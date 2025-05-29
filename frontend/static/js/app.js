// 前端主要逻辑，针对 upload.html 和 viewer.html 两页分别处理

document.addEventListener('DOMContentLoaded', () => {
  // 上传页逻辑
  const uploadBtn = document.getElementById('upload-btn');
  if (uploadBtn) {
    uploadBtn.onclick = async () => {
      const input = document.getElementById('file-input');
      if (!input.files.length) return;
      const form = new FormData();
      form.append('file', input.files[0]);
      // POST /upload 会触发重定向到 /viewer
      await fetch('/upload', { method: 'POST', body: form });
    };
  }

  // 渲染页逻辑
  const renderArea = document.getElementById('render-area');
  if (!renderArea) return;

  let scene, camera, renderer, controls, meshObj, midline;
  const angleDisplay = document.getElementById('angle-display');
  const extractBtn = document.getElementById('extract-btn');
  const selectBtn = document.getElementById('select-btn');

  // 初始化 Three.js 场景
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(
    45,
    renderArea.clientWidth / (window.innerHeight * 0.6),
    0.1,
    1000
  );
  camera.position.set(0, 0, 200);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(renderArea.clientWidth, window.innerHeight * 0.6);
  renderer.setClearColor(0xf5f5f5);
  renderArea.appendChild(renderer.domElement);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  // 灯光
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(0, 1, 1);
  scene.add(dirLight);

  // 射线拾取器
  const raycaster = new THREE.Raycaster();

  // 渲染循环
  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // 加载 OBJ 模型
  async function loadMesh() {
    const resp = await fetch('/api/mesh');
    const objText = await resp.text();
    const loader = new THREE.OBJLoader();
    meshObj = loader.parse(objText);
    scene.add(meshObj);
  }
  loadMesh();

  // 提取中轴线
  extractBtn.onclick = async () => {
    const res = await fetch('/api/extract-midline');
    const { midline: pts } = await res.json();
    if (midline) scene.remove(midline);
    const geo = new THREE.BufferGeometry().setFromPoints(
      pts.map(p => new THREE.Vector3(...p))
    );
    midline = new THREE.Line(
      geo,
      new THREE.LineBasicMaterial({ color: 0xff00ff, linewidth: 4 })
    );
    scene.add(midline);
  };

  // 选择面片
  selectBtn.onclick = () => {
    renderer.domElement.addEventListener('click', onPick, { once: true });
  };

  async function onPick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera({ x, y }, camera);
    const intersects = raycaster.intersectObject(meshObj, true);
    if (!intersects.length) return;
    const faceIndex = intersects[0].faceIndex;
    const resp = await fetch('/api/select-face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ faceIndex })
    });
    const data = await resp.json();

    // 清除旧高亮
    scene.traverse(obj => {
      if (obj.userData.highlight) scene.remove(obj);
    });

    // 高亮放大面
    const verts = data.expandedFace.vertices;
    const faces = data.expandedFace.faces;
    const expGeo = new THREE.BufferGeometry();
    expGeo.setAttribute('position', new THREE.Float32BufferAttribute(verts.flat(), 3));
    expGeo.setIndex(faces.flat());
    const expMesh = new THREE.Mesh(
      expGeo,
      new THREE.MeshBasicMaterial({ color: 0xff0000, transparent: true, opacity: 0.8 })
    );
    expMesh.userData.highlight = true;
    scene.add(expMesh);

    // 显示角度
    angleDisplay.textContent = `Angle: ${data.angle.toFixed(2)}°`;
  }
}
);