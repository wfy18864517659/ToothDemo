# 安装依赖（在命令行执行）
# pip install trimesh networkx pyvista pyvistaqt PyQt5

import sys
import numpy as np
import trimesh
import networkx as nx  # 用于图算法
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
        # 转换为 PyVista 格式
        faces = np.hstack([np.full((len(self.mesh.faces), 1), 3), self.mesh.faces]).astype(np.int64)
        self.pv_mesh = pv.PolyData(self.mesh.vertices, faces)
        self.actor = self.vtk_widget.add_mesh(self.pv_mesh, color='tan', show_edges=True)

        # 点击事件绑定（单元拾取）
        self.vtk_widget.enable_cell_picking(callback=self.on_pick, through=False)

        # 存储中轴线点集
        self.midline = None

    def extract_midline(self):
        """
        使用网格顶点邻接图近似提取骨架：
        1. 构建带权的顶点邻接图（边权为顶点间欧氏距离）
        2. Dijkstra 两次寻找直径路径，作为中轴线近似
        """
        # 1. 获取邻接矩阵并构建带权图
        graph = self.mesh.vertex_adjacency_graph  # networkx Graph
        # 确保每条边加权为顶点欧氏距离
        for u, v, data in graph.edges(data=True):
            if 'weight' not in data:
                p_u = self.mesh.vertices[u]
                p_v = self.mesh.vertices[v]
                data['weight'] = np.linalg.norm(p_u - p_v)

        # 2. 从顶点0做一次最短路径，找最远节点A
        lengths_0 = nx.single_source_dijkstra_path_length(graph, source=0, weight='weight')
        node_a = max(lengths_0, key=lengths_0.get)
        # 3. 从A再做一次，找最远节点B
        lengths_a = nx.single_source_dijkstra_path_length(graph, source=node_a, weight='weight')
        node_b = max(lengths_a, key=lengths_a.get)
        # 4. 提取A到B的路径作为中轴线近似
        path = nx.shortest_path(graph, source=node_a, target=node_b, weight='weight')
        self.midline = np.array([self.mesh.vertices[i] for i in path])

        # 可视化：绘制中轴曲线
        if hasattr(self, 'line_actor'):
            self.vtk_widget.remove_actor(self.line_actor)
        self.line_actor = self.vtk_widget.add_lines(self.midline, color='red', width=4)
        self.vtk_widget.reset_camera()

    def on_pick(self, cell_id):
        """
        当点击某个三角面时，计算该面法向量与中轴线方向的夹角，并弹窗显示。
        """
        if cell_id is None or self.midline is None:
            return
        # 获取面片顶点索引
        face = self.mesh.faces[cell_id]
        # 计算面法向量
        normal = self.mesh.face_normals[cell_id]
        # 中轴线主方向：起点到终点向量归一化
        axis_vec = self.midline[-1] - self.midline[0]
        axis_vec /= np.linalg.norm(axis_vec)
        # 计算夹角（面法向量与轴向量之间）
        angle = np.degrees(np.arccos(np.clip(np.dot(normal, axis_vec), -1.0, 1.0)))
        QtWidgets.QMessageBox.information(
            self,
            "夹角结果",
            f"所选面ID {cell_id} 与中轴线夹角: {angle:.2f}°"
        )

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = ToothViewer('/home/wushaoxuan/PycharmProjects/ToothDemo/data/10303a1404w01.obj')  # 替换为你的 OBJ 文件路径
    viewer.show()
    sys.exit(app.exec_())
