// app.js - 前端主要逻辑，针对 upload.html 和 viewer.html 两页分别处理

document.addEventListener('DOMContentLoaded', () => {
  // 上传页逻辑
  const uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.onsubmit = () => {
      const spinner = document.getElementById('spinner');
      spinner.classList.remove('hidden');
    };
  }

  // 查看页逻辑
  const renderArea = document.getElementById('render-area');
  if (!renderArea) return;

  // Three.js 初始化
  const scene = new THREE.Scene();
  const width = renderArea.clientWidth;
  const height = window.innerHeight * 0.9;
  const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 5000);
  camera.position.set(0, 0, 300);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setClearColor(0xf0f0f0);
  renderArea.appendChild(renderer.domElement);

  // Controls
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;

  // Lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(100, 100, 100);
  scene.add(dirLight);

  // Raycaster
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();

  // Globals
  let meshObj = null;
  let midline = null;
  const angleDisplay = document.getElementById('angle-display');
  const extractBtn = document.getElementById('extract-btn');
  const selectBtn = document.getElementById('select-btn');

  // Animation loop
  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // Load and setup mesh
  async function loadMesh() {
    const res = await fetch('/api/mesh');
    const objText = await res.text();
    meshObj = new THREE.OBJLoader().parse(objText);
    meshObj.traverse(child => {
      if (child.isMesh) {
        child.material = new THREE.MeshLambertMaterial({
          color: 0xaaaaaa,
          side: THREE.DoubleSide
        });
        child.geometry.computeVertexNormals();
      }
    });

    // Scale & Center
    const box = new THREE.Box3().setFromObject(meshObj);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = (Math.min(width, height) * 0.8) / maxDim;
    meshObj.scale.set(scale, scale, scale);
    box.setFromObject(meshObj);
    const center = box.getCenter(new THREE.Vector3());
    meshObj.position.sub(center);

    scene.add(meshObj);
    camera.position.set(0, 0, maxDim * scale * 1.5);
    controls.target.copy(new THREE.Vector3(0, 0, 0));
    controls.update();
  }
  loadMesh();

  // Extract midline
  extractBtn.onclick = async () => {
    if (!meshObj) return;
    const res = await fetch('/api/extract-midline');
    const { midline: pts } = await res.json();
    if (midline) scene.remove(midline);
    const transformed = pts.map(p => {
      return new THREE.Vector3(...p)
        .multiplyScalar(meshObj.scale.x)
        .add(meshObj.position);
    });
    const geo = new THREE.BufferGeometry().setFromPoints(transformed);
    midline = new THREE.Line(
      geo,
      new THREE.LineBasicMaterial({ color: 0xff00ff, linewidth: 6, depthTest: false })
    );
    scene.add(midline);
  };

  // Pick face on click
  selectBtn.onclick = () => {
    if (!meshObj) return;
    controls.enabled = false;
    renderer.domElement.style.cursor = 'crosshair';
    renderer.domElement.addEventListener('click', onPick, { once: true });
  };

  async function onPick(event) {
    renderer.domElement.style.cursor = 'default';
    controls.enabled = true;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObject(meshObj, true);
    console.log('hits:', hits);
    if (!hits.length) return;
    const hit = hits[0];

    // Clear old highlights
    scene.children
      .filter(o => o.userData.highlight)
      .forEach(o => scene.remove(o));

    // Mark point
    const ptSize = meshObj.scale.x * 0.5;
    const ptMesh = new THREE.Mesh(
      new THREE.SphereGeometry(ptSize, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xff0000, depthTest: false })
    );
    ptMesh.position.copy(hit.point);
    ptMesh.userData.highlight = true;
    scene.add(ptMesh);

    // Face vertices directly from hit.face.a/b/c
    const geom = hit.object.geometry;
    const posAttr = geom.attributes.position;
    const { a, b, c } = hit.face;
    const toWorld = v => v.multiplyScalar(meshObj.scale.x).add(meshObj.position);
    const vA = new THREE.Vector3().fromBufferAttribute(posAttr, a);
    const vB = new THREE.Vector3().fromBufferAttribute(posAttr, b);
    const vC = new THREE.Vector3().fromBufferAttribute(posAttr, c);
    [vA, vB, vC].forEach(v => toWorld(v));

    // Highlight triangle (green)
    const triGeo = new THREE.BufferGeometry().setFromPoints([vA, vB, vC]);
    triGeo.setIndex([0, 1, 2]);
    const triMat = new THREE.MeshBasicMaterial({
      color: 0x00ff00,
      side: THREE.DoubleSide,
      depthTest: false,
      depthWrite: false
    });
    const triMesh = new THREE.Mesh(triGeo, triMat);
    triMesh.userData.highlight = true;
    scene.add(triMesh);

    // Expanded region using same triangle center, radius = distance*10
    const center = vA.clone().add(vB).add(vC).divideScalar(3);
    const radius = vA.distanceTo(center) * 10;
    const circGeo = new THREE.CircleGeometry(radius, 32);
    const circMat = new THREE.MeshBasicMaterial({
      color: 0xffff00,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.5,
      depthTest: false,
      depthWrite: false
    });
    const circMesh = new THREE.Mesh(circGeo, circMat);
    circMesh.position.copy(center);
    circMesh.lookAt(hit.face.normal);
    circMesh.userData.highlight = true;
    scene.add(circMesh);

    // Compute and display angle
    if (!midline) return;
    const arr = midline.geometry.attributes.position.array;
    const P0 = new THREE.Vector3(arr[0], arr[1], arr[2]);
    const P1 = new THREE.Vector3(arr[arr.length - 3], arr[arr.length - 2], arr[arr.length - 1]);
    const axis = P1.clone().sub(P0).normalize();
    const normal = hit.face.normal.clone();
    const angle = Math.acos(Math.max(-1, Math.min(1, normal.dot(axis)))) * 180 / Math.PI;
    angleDisplay.textContent = `Angle: ${angle.toFixed(2)}°`;
  }
});