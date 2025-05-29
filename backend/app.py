import os
from flask import Flask, request, jsonify, render_template, redirect, url_for
import trimesh
import numpy as np
from sklearn.decomposition import PCA

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
current_mesh = None

@app.route('/')
def upload_page():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    global current_mesh
    f = request.files['file']
    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    current_mesh = trimesh.load(path)
    return redirect(url_for('viewer_page'))

@app.route('/viewer')
def viewer_page():
    return render_template('viewer.html')

@app.route('/api/mesh')
def mesh():
    export = current_mesh.export(file_type='obj')
    return export, 200, {'Content-Type': 'text/plain'}

@app.route('/api/extract-midline')
def extract_midline():
    verts = current_mesh.vertices
    pca = PCA(n_components=3).fit(verts)
    axis = pca.components_[0]
    centroid = verts.mean(axis=0)
    proj = np.dot(verts - centroid, axis)
    half = (proj.max() - proj.min())/2
    pts = np.vstack([centroid - axis*half, centroid + axis*half])
    return jsonify({'midline': pts.tolist()})

@app.route('/api/select-face', methods=['POST'])
def select_face():
    data = request.get_json()
    fid = data['faceIndex']
    tri = current_mesh.vertices[current_mesh.faces[fid]]
    centroid = tri.mean(axis=0)
    verts_exp = centroid + 20*(tri - centroid)
    faces_exp = [[3,0,1,2]]
    normal = current_mesh.face_normals[fid]
    axis = PCA(n_components=3).fit(current_mesh.vertices).components_[0]
    angle = float(np.degrees(np.arccos(np.clip(np.dot(normal,axis)/(np.linalg.norm(normal)*np.linalg.norm(axis)),-1,1))))
    return jsonify({
        'expandedFace': {'vertices': verts_exp.tolist(), 'faces': faces_exp},
        'angle': angle
    })

if __name__ == '__main__':
    app.run(debug=True)