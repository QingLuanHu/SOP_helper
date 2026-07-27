from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class RightQuizPanel(QWidget):
    """右侧考核模式（题库、答题、分数）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标题 + 分数
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.title = QLabel("📝 考核模式 - 开卷答题")
        self.title.setStyleSheet("font-size: 18px; font-weight: bold; color: #c0392b; padding: 8px 12px; background: #fef9e7; border-radius: 4px;")
        header_layout.addWidget(self.title)

        header_layout.addStretch()

        self.score_label = QLabel("")
        self.score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.score_label.setStyleSheet("font-size: 36px; font-weight: bold; color: #2c3e50; padding: 4px 16px;")
        header_layout.addWidget(self.score_label)

        layout.addWidget(header_widget)

        # 滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: white; border: none;")
        self.container = QWidget()
        self.container.setStyleSheet("background: white;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(16, 16, 16, 16)
        self.container_layout.setSpacing(16)
        self.container_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.open_pdf_btn = QPushButton("📄 打开PDF")
        self.open_pdf_btn.setFixedHeight(36)
        self.open_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.open_pdf_btn.clicked.connect(self.parent.on_quiz_open_pdf)
        action_layout.addWidget(self.open_pdf_btn, 1)

        self.restart_btn = QPushButton("🔄 重新答题")
        self.restart_btn.setFixedHeight(36)
        self.restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #e67e22; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.restart_btn.clicked.connect(self.parent.on_quiz_restart)
        action_layout.addWidget(self.restart_btn, 1)

        self.save_btn = QPushButton("💾 保存答案")
        self.save_btn.setFixedHeight(36)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.save_btn.clicked.connect(self.parent.on_quiz_save_answers)
        action_layout.addWidget(self.save_btn, 1)

        self.submit_btn = QPushButton("📤 提交答案")
        self.submit_btn.setFixedHeight(36)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.submit_btn.clicked.connect(self.parent.submit_quiz)
        self.submit_btn.setEnabled(False)
        action_layout.addWidget(self.submit_btn, 1)

        layout.addLayout(action_layout)

        # 禁用初始按钮
        self.open_pdf_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

    def clear_quiz(self):
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.score_label.setText("")

    def add_widget(self, widget):
        self.container_layout.insertWidget(self.container_layout.count() - 1, widget)

    def set_score(self, score, color):
        self.score_label.setText(f"{score}分")
        if color:
            self.score_label.setStyleSheet(
                f"font-size: 36px; font-weight: bold; color: rgb({color[0]},{color[1]},{color[2]}); padding: 4px 16px;"
            )

    def enable_buttons(self, enabled=True):
        self.open_pdf_btn.setEnabled(enabled)
        self.restart_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)

    def enable_submit(self, enabled=True):
        self.submit_btn.setEnabled(enabled)