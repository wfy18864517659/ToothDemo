# 安装依赖（在命令行执行）
# pip install trimesh pyvista pyvistaqt PyQt5 numpy sklearn

import sys
import numpy as np
import trimesh
from sklearn.decomposition import PCA
from PyQt5 import QtWidgets
import pyvista as pv
from pyvistaqt import QtInteractor

class MidlineExtractor:
    """
    使用 PCA 提取一条穿过牙齿中心、平行于生长方向的直线作为中轴线。
    """
    def __init__(self, mesh: trimesh.Trimesh):
        self.mesh = mesh

    def extract(self) -> np.ndarray:
        # 顶点云
        verts = self.mesh.vertices
        # PCA 提取主方向（第一分量）
        pca = PCA(n_components=3)
        pca.fit(verts)
        axis = pca.components_[0]
        # 计算重心
        centroid = verts.mean(axis=0)
        # 确定线段长度（适当倍增最大投影长度）
        proj_lengths = np.dot(verts - centroid, axis)
        half_len = (proj_lengths.max() - proj_lengths.min()) / 2
        # 生成两端点
        pt1 = centroid - axis * half_len
        pt2 = centroid + axis * half_len
        return np.vstack([pt1, pt2])  # shape (2,3)

class MeshViewer(QtWidgets.QMainWindow):
    def __init__(self, mesh_path: str):
        super().__init__()
        self.setWindowTitle("三维牙齿中轴线及角度分析")
        self.resize(600, 800)

        # 主 Widget
        self.frame = QtWidgets.QFrame()
        vlayout = QtWidgets.QVBoxLayout(self.frame)

        # PyVista 渲染窗口
        self.vtk_widget = QtInteractor(self.frame)
        vlayout.addWidget(self.vtk_widget)

        # 控制按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_extract = QtWidgets.QPushButton("提取中轴线")
        self.btn_extract.clicked.connect(self.on_extract)
        btn_layout.addWidget(self.btn_extract)
        vlayout.addLayout(btn_layout)

        self.setCentralWidget(self.frame)

        # 加载并平滑网格
        self.mesh = trimesh.load(mesh_path)
        self.pv_mesh = pv.PolyData(self.mesh.vertices, np.hstack([np.full((len(self.mesh.faces),1),3), self.mesh.faces]).astype(np.int64))
        self.pv_mesh = self.pv_mesh.smooth(n_iter=20)  # 平滑

        # 添加主体网格，使用 Phong 着色
        self.actor = self.vtk_widget.add_mesh(
            self.pv_mesh,
            color='lightgray',
            smooth_shading=True,
            show_edges=False
        )

        # 绑定点击事件：拾取面片
        self.vtk_widget.enable_cell_picking(callback=self.on_pick, through=False)
        self.highlight_actor = None
        self.midline = None

    def on_extract(self):
        extractor = MidlineExtractor(self.mesh)
        line_pts = extractor.extract()
        # 可视化中轴线
        if self.midline is not None:
            self.vtk_widget.remove_actor(self.midline)
        self.midline = self.vtk_widget.add_lines(line_pts, color='red', width=4)
        self.vtk_widget.reset_camera()

    def on_pick(self, cell_id: int):
        if cell_id is None or self.midline is None:
            return
        # 高亮所选三角面
        cell = self.pv_mesh.extract_cells([cell_id])
        if self.highlight_actor:
            self.vtk_widget.remove_actor(self.highlight_actor)
        self.highlight_actor = self.vtk_widget.add_mesh(
            cell,
            color='yellow',
            line_width=2,
            opacity=0.6,
            style='wireframe'
        )
        # 计算角度
        normal = np.array(self.mesh.face_normals[cell_id])
        axis_vec = (self.midline.points[-1] - self.midline.points[0])
        axis_vec = axis_vec / np.linalg.norm(axis_vec)
        angle = np.degrees(np.arccos(np.clip(np.dot(normal, axis_vec), -1.0, 1.0)))
        QtWidgets.QMessageBox.information(
            self,
            "夹角结果",
            f"面 ID {cell_id} 与中轴线夹角: {angle:.2f}°"
        )

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = MeshViewer('/home/wushaoxuan/PycharmProjects/ToothDemo/data/10303a1404w01.obj')  # 替换为你的 OBJ 文件路径
    viewer.show()
    sys.exit(app.exec_())
