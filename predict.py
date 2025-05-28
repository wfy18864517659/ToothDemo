# 导入必要库
import sys
import numpy as np
import trimesh
from PyQt5 import QtWidgets
import pyvista as pv
from pyvistaqt import QtInteractor

class ToothViewer(QtWidgets.QMainWindow):
    def __init__(self, mesh_path):
        super().__init__()
        self.setWindowTitle("三维牙齿中轴线及角度分析")
        self.frame = QtWidgets.QFrame()
        self.layout = QtWidgets.QVBoxLayout()
        self.vtk_widget = QtInteractor(self.frame)
        self.layout.addWidget(self.vtk_widget)

        # 按钮：提取中轴线
        self.btn_extract = QtWidgets.QPushButton("提取中轴线")
        self.btn_extract.clicked.connect(self.extract_midline)
        self.layout.addWidget(self.btn_extract)

        self.frame.setLayout(self.layout)
        self.setCentralWidget(self.frame)

        # 加载网格
        self.mesh = trimesh.load(mesh_path)
        # PyVista 转换
        self.pv_mesh = pv.PolyData(self.mesh.vertices, np.hstack([np.full((len(self.mesh.faces),1),3), self.mesh.faces]).astype(np.int64))
        self.actor = self.vtk_widget.add_mesh(self.pv_mesh, color='tan', show_edges=True)

        # 点击事件绑定
        self.vtk_widget.enable_cell_picking(callback=self.on_pick, through=False)

        # 存储中轴线
        self.midline = None

    def extract_midline(self):
        """
        使用曲线骨架提取算法（基于 Trimesh Skeleton 或外部库）
        """
        # 这里示例调用 Trimesh Poisson Skeleton
        from trimesh.skeleton import mesh_to_graph
        graph = mesh_to_graph(self.mesh)
        # 提取最长路径作为主中轴
        lengths = nx.single_source_dijkstra_path_length(graph, 0)
        far = max(lengths, key=lengths.get)
        path = nx.shortest_path(graph, source=0, target=far)
        self.midline = np.array([self.mesh.vertices[i] for i in path])

        # 可视化中轴线
        if hasattr(self, 'line_actor'):
            self.vtk_widget.remove_actor(self.line_actor)
        self.line_actor = self.vtk_widget.add_lines(self.midline, color='red', width=4)
        self.vtk_widget.reset_camera()

    def on_pick(self, cell):
        """
        当点击某个三角面时，计算该面法向量与中轴线方向的夹角
        """
        if cell is None or self.midline is None:
            return
        # 取面中心点
        cell_id = cell
        face = self.mesh.faces[cell_id]
        # 法向量
        normal = self.mesh.face_normals[cell_id]
        # 中轴线方向：用中轴线的整体方向（首尾向量）
        axis_vec = self.midline[-1] - self.midline[0]
        axis_vec /= np.linalg.norm(axis_vec)
        # 计算夹角
        angle = np.degrees(np.arccos(np.clip(np.dot(normal, axis_vec), -1,1)))
        QtWidgets.QMessageBox.information(self, "夹角结果", f"面 {cell_id} 与中轴线夹角: {angle:.2f}°")

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = ToothViewer('tooth.obj')  # 替换为你的 OBJ 文件路径
    viewer.show()
    sys.exit(app.exec_())
