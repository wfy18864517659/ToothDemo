from PyQt5 import QtWidgets, QtCore


class FileLoaderPage(QtWidgets.QWidget):
    """文件上传页面，上传后切换到中轴线提取页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.btn_open = QtWidgets.QPushButton("上传 OBJ 文件")
        self.progress = QtWidgets.QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.btn_open)
        layout.addWidget(self.progress)
        self.btn_open.clicked.connect(self.open_file)

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择 OBJ 文件", "", "OBJ Files (*.obj)")
        if not path:
            return
        # 模拟加载进度
        for i in range(1, 101):
            QtCore.QThread.msleep(5)
            self.progress.setValue(i)
            QtWidgets.QApplication.processEvents()
        # 通知主界面切换
        self.parent().load_mesh(path)