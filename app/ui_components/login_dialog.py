from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录工位SOP助手")
        self.setModal(True)
        self.resize(300, 150)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("请输入员工姓名："))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("为确保名字唯一性，最好输入 工号+姓名，例如：12345张三")
        layout.addWidget(self.name_edit)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("登录")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_username(self):
        return self.name_edit.text().strip() or "未命名用户"