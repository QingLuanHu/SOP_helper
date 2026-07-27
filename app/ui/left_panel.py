from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt


class LeftPanel(QWidget):
    """左侧文件列表"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title = QLabel("📂 关联文件")
        self.title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50; padding-bottom: 6px;")
        layout.addWidget(self.title)

        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Microsoft YaHei", 11))
        self.file_list.setStyleSheet("""
            QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #e0e0e0; }
            QListWidget::item:hover { background-color: #f0f7ff; }
        """)
        self.file_list.itemClicked.connect(self.parent.on_file_clicked)
        layout.addWidget(self.file_list)

    def clear(self):
        self.file_list.clear()

    def add_item(self, text, color=None):
        item = QListWidgetItem(text)
        if color:
            item.setForeground(color)
        self.file_list.addItem(item)

    def count(self):
        return self.file_list.count()

    def set_placeholder(self, text):
        self.clear()
        self.add_item(text, QColor("#999999"))