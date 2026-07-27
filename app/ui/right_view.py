from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt


class RightViewPanel(QWidget):
    """右侧查看模式（工站动态推送）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title = QLabel("📢 工站动态推送")
        self.title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50; padding-bottom: 6px;")
        layout.addWidget(self.title)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self.parent.on_anchor_clicked)
        self.browser.setStyleSheet("""
            font-size: 12pt; 
            line-height: 1.8; 
            background-color: #fafafa; 
            border: 1px solid #ddd; 
            border-radius: 4px;
        """)
        layout.addWidget(self.browser)

    def set_html(self, html):
        self.browser.setHtml(html)