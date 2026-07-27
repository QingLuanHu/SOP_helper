from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class TopBar(QWidget):
    """顶部工具栏：登录、工站、分类、搜索、考核切换"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)

        CONTROL_HEIGHT = 40
        FONT_SIZE = 11

        # 左区域（登录 + 考核）
        left_area = QWidget()
        left_area_layout = QHBoxLayout(left_area)
        left_area_layout.setContentsMargins(0, 0, 0, 0)
        left_area_layout.setSpacing(12)

        col0_widget = QWidget()
        col0_layout = QVBoxLayout(col0_widget)
        col0_layout.setContentsMargins(0, 0, 0, 0)
        col0_layout.setSpacing(8)
        col0_layout.addStretch()

        # 登录行
        login_row = QWidget()
        login_row_layout = QHBoxLayout(login_row)
        login_row_layout.setContentsMargins(0, 0, 0, 0)
        login_row_layout.setSpacing(8)

        self.user_label = QLabel("👤 未登录")
        self.user_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12pt;")
        login_row_layout.addWidget(self.user_label)

        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedSize(70, CONTROL_HEIGHT)
        self.login_btn.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.login_btn.clicked.connect(self.parent.toggle_login)
        login_row_layout.addWidget(self.login_btn)
        login_row_layout.addStretch()
        col0_layout.addWidget(login_row)

        # 考核模式
        self.exam_toggle = QPushButton("📝 考核模式")
        self.exam_toggle.setCheckable(True)
        self.exam_toggle.setFixedHeight(CONTROL_HEIGHT)
        self.exam_toggle.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.exam_toggle.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 4px 16px;
                min-width: 100px;
            }
            QPushButton:checked { background-color: #e74c3c; }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.exam_toggle.toggled.connect(self.parent.on_exam_mode_toggled)
        exam_container = QWidget()
        exam_layout = QHBoxLayout(exam_container)
        exam_layout.setContentsMargins(0, 0, 0, 0)
        exam_layout.addWidget(self.exam_toggle)
        exam_layout.addStretch()
        col0_layout.addWidget(exam_container)
        col0_layout.addStretch()
        left_area_layout.addWidget(col0_widget, 1)

        # 右区域（工站 + 分类）
        col1_widget = QWidget()
        col1_layout = QVBoxLayout(col1_widget)
        col1_layout.setContentsMargins(0, 0, 0, 0)
        col1_layout.setSpacing(8)
        col1_layout.addStretch()

        # 工站行
        station_row = QWidget()
        station_row_layout = QHBoxLayout(station_row)
        station_row_layout.setContentsMargins(0, 0, 0, 0)
        station_row_layout.setSpacing(8)

        self.station_label = QLabel("工站:")
        self.station_label.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        station_row_layout.addWidget(self.station_label)

        self.station_combo = QComboBox()
        self.station_combo.setMinimumWidth(180)
        self.station_combo.setFixedHeight(CONTROL_HEIGHT)
        self.station_combo.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.station_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                color: black;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 20px;
            }
        """)
        self.station_combo.currentTextChanged.connect(self.parent.on_station_changed)
        station_row_layout.addWidget(self.station_combo)
        station_row_layout.addStretch()
        col1_layout.addWidget(station_row)

        # 分类复选框
        checkbox_container = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(16)

        self.checkbox_general = QCheckBox("通用操作")
        self.checkbox_general.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.checkbox_general.setStyleSheet("padding: 4px;")
        self.checkbox_general.stateChanged.connect(self.parent.on_category_filter_changed)
        checkbox_layout.addWidget(self.checkbox_general)

        self.checkbox_product = QCheckBox("产品相关")
        self.checkbox_product.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.checkbox_product.setStyleSheet("padding: 4px;")
        self.checkbox_product.stateChanged.connect(self.parent.on_category_filter_changed)
        checkbox_layout.addWidget(self.checkbox_product)

        checkbox_layout.addStretch()
        col1_layout.addWidget(checkbox_container)
        col1_layout.addStretch()
        left_area_layout.addWidget(col1_widget, 1)

        layout.addWidget(left_area, 1)

        # 右侧搜索栏
        search_area = QWidget()
        search_layout = QVBoxLayout(search_area)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)
        search_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索SOP文件名...")
        self.search_input.setFixedHeight(CONTROL_HEIGHT)
        self.search_input.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 4px 10px;
                background-color: white;
            }
        """)
        self.search_input.textChanged.connect(self.parent.on_search_changed)
        search_layout.addWidget(self.search_input, alignment=Qt.AlignCenter)
        search_layout.addStretch()

        layout.addWidget(search_area, 1)

        # 保存引用
        self.left_area = left_area
        self.search_area = search_area

    def set_stations(self, stations):
        self.station_combo.clear()
        self.station_combo.addItems(stations if stations else ["无工站"])
        self.station_combo.setCurrentIndex(0)

    def get_current_station(self):
        return self.station_combo.currentText()

    def set_search_visible(self, visible):
        self.search_input.setVisible(visible)

    def clear_search(self):
        self.search_input.clear()