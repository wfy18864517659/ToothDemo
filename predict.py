# 安装依赖
# pip install trimesh pyvista pyvistaqt PyQt5 numpy sklearn scipy

import sys
import numpy as np
import trimesh
from sklearn.decomposition import PCA
from scipy.spatial import cKDTree
from PyQt5 import QtWidgets, QtCore
import pyvista as pv
from pyvistaqt import QtInteractor

class MidlineExtractor:
    """
    使用 PCA 提取笔直中轴线。
    """
    def __init__(self, mesh: trimesh.Trimesh):
        self.mesh = mesh

    def extract(self) -> np.ndarray:
        verts = self.mesh.vertices
        pca = PCA(n_components=3)
        pca.fit(verts)
        axis = pca.components_[0]
        centroid = verts.mean(axis=0)
        proj = np.dot(verts - centroid, axis)
        half_len = (proj.max() - proj.min()) / 2
        return np.vstack([centroid - axis * half_len,
                          centroid + axis * half_len])

class FileLoaderPage(QtWidgets.QWidget):
    """文件上传页面，加载完成后切换到查看页面"""
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)

        title = QtWidgets.QLabel("牙齿模型中轴线分析")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:bold;")
        layout.addWidget(title)

        self.btn_open = QtWidgets.QPushButton("上传 OBJ 文件")
        self.btn_open.setFixedHeight(40)
        self.btn_open.setStyleSheet(
            "font-size:16px; background:#5A9BD5; color:white; border-radius:5px;"
        )
        layout.addWidget(self.btn_open, alignment=QtCore.Qt.AlignCenter)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setFixedHeight(20)
        layout.addWidget(self.progress)

        layout.addStretch()

        self.btn_open.clicked.connect(self.open_file)

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择 OBJ 文件", "", "OBJ Files (*.obj)"
        )
        if not path:
            return
        for i in range(1, 101):
            QtCore.QThread.msleep(5)
            self.progress.setValue(i)
            QtWidgets.QApplication.processEvents()
        self.main_window.load_mesh(path)

class MeshViewerPage(QtWidgets.QWidget):
    """中轴线提取与点选面片页面"""
    def __init__(self, mesh_path: str):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 按钮行
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_extract = QtWidgets.QPushButton("提取中轴线")
        self.btn_select = QtWidgets.QPushButton("选择点")
        for btn in (self.btn_extract, self.btn_select):
            btn.setCheckable(True)
            btn.setFixedHeight(32)
        btn_layout.addWidget(self.btn_extract)
        btn_layout.addWidget(self.btn_select)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # PyVista 视图
        self.plotter = QtInteractor(self)
        self.plotter.enable_anti_aliasing()
        self.plotter.enable_eye_dome_lighting()
        layout.addWidget(self.plotter)

        # 加载网格
        self.mesh = trimesh.load(mesh_path)
        faces = np.hstack([
            np.full((len(self.mesh.faces), 1), 3), self.mesh.faces
        ]).astype(np.int64)
        self.pv_mesh = pv.PolyData(self.mesh.vertices, faces).smooth(n_iter=30)
        self.plotter.add_mesh(
            self.pv_mesh,
            color='#D3D3D3',
            opacity=0.25,
            smooth_shading=True
        )

        # 顶点 KDTree
        self.kdtree = cKDTree(self.mesh.vertices)

        # 状态
        self.midline_actor = None
        self.midline_pts = None
        self.highlight_orig = None
        self.highlight_expanded = None
        self.highlight_ring = None
        self.text_actor = None

        # 事件
        self.btn_extract.clicked.connect(self.on_extract)
        self.btn_select.clicked.connect(self.on_toggle_select)

    def on_extract(self):
        # 退出选择
        self.btn_select.setChecked(False)
        self.plotter.disable_picking()
        extractor = MidlineExtractor(self.mesh)
        pts = extractor.extract()
        self.midline_pts = pts
        if self.midline_actor:
            self.plotter.remove_actor(self.midline_actor)
        self.midline_actor = self.plotter.add_lines(pts, color='#FF00FF', width=8)
        self.plotter.reset_camera()

    def on_toggle_select(self, checked):
        if checked:
            # 启用点拾取
            self.btn_extract.setChecked(False)
            self.plotter.enable_point_picking(
                callback=self.on_pick_point,
                use_picker=True,
                show_message=False
            )
        else:
            self.plotter.disable_picking()

    def on_pick_point(self, point, *_):
        # 取消选择模式
        self.btn_select.setChecked(False)
        self.plotter.disable_picking()
        # 找最近顶点
        _, vid = self.kdtree.query(point)
        # 顶点对应面片列表，默认第一个
        face_idxs = np.where(self.mesh.faces == vid)[0]
        if face_idxs.size == 0 or self.midline_pts is None:
            return
        fid = int(face_idxs[0])
        # 邻环面
        neighbors = [
            b if a == fid else a
            for a, b in self.mesh.face_adjacency
            if a == fid or b == fid
        ]
        # 清除旧高亮
        for actor in (self.highlight_orig, self.highlight_expanded, self.highlight_ring, self.text_actor):
            if actor:
                self.plotter.remove_actor(actor)
        # 高亮原面 (蓝色, 更醒目)
        orig = self.pv_mesh.extract_cells(np.array([fid], dtype=int))
        self.highlight_orig = self.plotter.add_mesh(orig, color='blue', opacity=1.0)
        # 扩大三角面片：按重心放大1.5倍 (明亮红)
        tri_verts = self.mesh.vertices[self.mesh.faces[fid]]
        centroid = tri_verts.mean(axis=0)
        verts_exp = centroid + 15 * (tri_verts - centroid)
        faces_exp = np.array([[3, 0, 1, 2]])
        mesh_exp = pv.PolyData(verts_exp, faces_exp)
        self.highlight_expanded = self.plotter.add_mesh(
            mesh_exp, color='red', opacity=0.8, smooth_shading=True
        )
        # 邻环
        if neighbors:
            ring = self.pv_mesh.extract_cells(np.array(neighbors, dtype=int))
            self.highlight_ring = self.plotter.add_mesh(ring, color='#32CD32', style='wireframe', line_width=4)
        # 计算并显示夹角
        normal = self.mesh.face_normals[fid]
        p0, p1 = self.midline_pts[0], self.midline_pts[-1]
        axis_vec = p1 - p0
        axis_vec /= np.linalg.norm(axis_vec)
        angle = np.degrees(np.arccos(np.clip(np.dot(normal, axis_vec), -1, 1)))
        self.text_actor = self.plotter.add_text(
            f"Angle: {angle:.2f}\u00b0",
            position='upper_right', color='white', font_size=16
        )
        self.plotter.render()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("牙齿中轴线分析平台")
        self.resize(900, 700)
        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)
        self.loader = FileLoaderPage(self)
        self.stack.addWidget(self.loader)

    def load_mesh(self, path):
        viewer = MeshViewerPage(path)
        self.stack.addWidget(viewer)
        self.stack.setCurrentWidget(viewer)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
