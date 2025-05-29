# 安装依赖
# pip install trimesh pyvista pyvistaqt PyQt5 numpy sklearn

import sys
import numpy as np
import trimesh
from sklearn.decomposition import PCA
from PyQt5 import QtWidgets, QtCore, QtGui
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
        return np.vstack([centroid - axis*half_len, centroid + axis*half_len])

class FileLoaderPage(QtWidgets.QWidget):
    """文件上传页面，上传后调用回调切换页面"""
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(50,50,50,50)
        self.btn_open = QtWidgets.QPushButton("上传 OBJ 文件")
        self.btn_open.setFixedHeight(40)
        self.btn_open.setStyleSheet("font-size:16px; background:#5A9BD5; color:white; border-radius:5px;")
        self.progress = QtWidgets.QProgressBar()
        self.progress.setFixedHeight(20)
        layout.addWidget(self.btn_open, alignment=QtCore.Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(self.progress)
        self.btn_open.clicked.connect(self.open_file)

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择 OBJ 文件", "", "OBJ Files (*.obj)")
        if not path:
            return
        for i in range(1, 101):
            QtCore.QThread.msleep(5)
            self.progress.setValue(i)
            QtWidgets.QApplication.processEvents()
        self.main_window.load_mesh(path)

class MeshViewerPage(QtWidgets.QWidget):
    def __init__(self, mesh_path:str):
        super().__init__()
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)
        # 工具栏
        toolbar = QtWidgets.QFrame()
        toolbar.setFixedHeight(50)
        toolbar.setStyleSheet("background:#EEEEEE;")
        tb_layout = QtWidgets.QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10,5,10,5)
        self.btn_extract = QtWidgets.QPushButton("提取中轴线")
        self.btn_select = QtWidgets.QPushButton("选择面片")
        for btn in (self.btn_extract, self.btn_select):
            btn.setCheckable(True)
            btn.setStyleSheet("font-size:14px; padding:8px; border:1px solid #CCC; border-radius:4px;")
            tb_layout.addWidget(btn)
        tb_layout.addStretch()
        main_layout.addWidget(toolbar)
        # 渲染窗口
        self.plotter = QtInteractor(self)
        self.plotter.enable_anti_aliasing()
        self.plotter.enable_eye_dome_lighting()
        main_layout.addWidget(self.plotter)

        # 加载并渲染网格
        self.tri_mesh = trimesh.load(mesh_path)
        faces = np.hstack([np.full((len(self.tri_mesh.faces),1),3), self.tri_mesh.faces]).astype(np.int64)
        self.pv_mesh = pv.PolyData(self.tri_mesh.vertices, faces).smooth(n_iter=30)
        self.plotter.add_mesh(self.pv_mesh, color='#D3D3D3', opacity=0.25, smooth_shading=True)

        # 状态
        self.midline_actor = None
        self.highlight_orig = None
        self.highlight_ring = None
        self.text_actor = None

        # 按钮事件
        self.btn_extract.clicked.connect(self.on_extract)
        self.btn_select.clicked.connect(self.on_toggle_select)
        self.selecting = False

    def on_extract(self):
        self.btn_select.setChecked(False)
        self.selecting = False
        extractor = MidlineExtractor(self.tri_mesh)
        pts = extractor.extract()
        if self.midline_actor:
            self.plotter.remove_actor(self.midline_actor)
        self.midline_actor = self.plotter.add_lines(pts, color='#FF00FF', width=8)
        self.plotter.reset_camera()

    def on_toggle_select(self, checked):
        self.selecting = checked
        if checked:
            self.btn_extract.setChecked(False)
            self.plotter.enable_cell_picking(callback=self.on_pick_cell, show_message=False)
        else:
            self.plotter.disable_picking()

    def on_pick_cell(self, cell_id:int):
        if not self.selecting or cell_id is None or not self.midline_actor:
            return
        # 确保单次
        self.btn_select.setChecked(False)
        self.selecting = False
        # 清除旧高亮
        for a in (self.highlight_orig, self.highlight_ring, self.text_actor):
            if a: self.plotter.remove_actor(a)
        # 原面和邻环
        adj = self.tri_mesh.face_adjacency
        neigh = [b if a==cell_id else a for a,b in adj if a==cell_id or b==cell_id]
        orig = self.pv_mesh.extract_cells(np.array([cell_id], dtype=int))
        ring = self.pv_mesh.extract_cells(np.array(neigh, dtype=int)) if neigh else None
        self.highlight_orig = self.plotter.add_mesh(orig, color='#FFD700', opacity=0.9)
        if ring:
            self.highlight_ring = self.plotter.add_mesh(ring, color='#32CD32', style='wireframe', line_width=4)
        # 计算角度并显示
        normal = self.tri_mesh.face_normals[cell_id]
        axis = self.midline_actor.points[-1] - self.midline_actor.points[0]
        axis /= np.linalg.norm(axis)
        angle = np.degrees(np.arccos(np.clip(np.dot(normal, axis), -1,1)))
        self.text_actor = self.plotter.add_text(f"Angle: {angle:.2f}\u00b0", position='upper_right', color='white', font_size=16)
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

if __name__=='__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
