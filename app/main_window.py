import sys
import re
import json
import os
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QRadialGradient

from app.core.data_loader import DATA_LOADER
from app.ui_components.pdf_viewer import PDFViewerDialog
from app.ui_components.login_dialog import LoginDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("工位SOP助手 - 智能工站系统")
        self.setWindowIcon(self.create_icon())
        self.setGeometry(120, 80, 1280, 820)

        # 核心数据
        self.knowledge_data = DATA_LOADER.get_knowledge_graph()
        self.station_to_pdfs = DATA_LOADER.get_station_to_pdfs()
        self.file_categories = DATA_LOADER.get_file_categories()
        self.all_stations = DATA_LOADER.get_all_stations()

        docs = self.knowledge_data.get("documents", [])
        self.pdf_to_doc = {doc.get("pdf_name", ""): True for doc in docs if doc.get("pdf_name")}

        self.current_station = self.all_stations[0] if self.all_stations else "无工站"
        self.logged_in = False
        self.current_user = ""
        self._current_selected_pdf = None

        # 考核模式数据
        self.quiz_records = {}
        self.records_file_path = None
        self.quiz_questions = []
        self.quiz_answer_widgets = []
        self.quiz_pdf_name = None
        self.quiz_version = None

        # 搜索相关
        self.search_index = []
        self.current_results = []

        self.init_ui()
        self.refresh_left_list()
        self.update_right_panel()

        QTimer.singleShot(200, self.sync_top_layout)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_data_update)
        self.update_timer.start(3600 * 1000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.setMinimumSize(800, 600)

        self.top_widget = self.create_top_bar()
        self.top_widget.setFixedHeight(144)
        self.top_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.top_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f7fa;
                border-radius: 6px;
                border: 1px solid #d0d7de;
            }
        """)
        main_layout.addWidget(self.top_widget)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        left_panel = self.create_left_panel()
        self.splitter.addWidget(left_panel)

        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.create_view_mode_panel())
        self.right_stack.addWidget(self.create_quiz_mode_panel())
        self.splitter.addWidget(self.right_stack)

        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self.sync_top_layout)
        main_layout.addWidget(self.splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | 请先登录")

        # 右侧版本信息容器
        version_widget = QWidget()
        version_layout = QHBoxLayout(version_widget)
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setSpacing(4)

        self.version_label = QLabel()
        self.version_label.setStyleSheet("color: #888;")
        self.update_version_label()
        version_layout.addWidget(self.version_label)

        # 刷新按钮（圆形箭头）
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setToolTip("检查数据更新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 18px;
                color: #888;
            }
            QPushButton:hover {
                color: #3498db;
            }
        """)
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        version_layout.addWidget(self.refresh_btn)

        self.status_bar.addPermanentWidget(version_widget)

    # ---------- 顶部工具栏 ----------
    def create_top_bar(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)

        CONTROL_HEIGHT = 40
        FONT_SIZE = 11

        self.top_left_area = QWidget()
        left_area_layout = QHBoxLayout(self.top_left_area)
        left_area_layout.setContentsMargins(0, 0, 0, 0)
        left_area_layout.setSpacing(12)

        col0_widget = QWidget()
        col0_layout = QVBoxLayout(col0_widget)
        col0_layout.setContentsMargins(0, 0, 0, 0)
        col0_layout.setSpacing(8)
        col0_layout.addStretch()

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
        self.login_btn.clicked.connect(self.toggle_login)
        login_row_layout.addWidget(self.login_btn)
        login_row_layout.addStretch()
        col0_layout.addWidget(login_row)

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
        self.exam_toggle.toggled.connect(self.on_exam_mode_toggled)
        exam_container = QWidget()
        exam_layout = QHBoxLayout(exam_container)
        exam_layout.setContentsMargins(0, 0, 0, 0)
        exam_layout.addWidget(self.exam_toggle)
        exam_layout.addStretch()
        col0_layout.addWidget(exam_container)
        col0_layout.addStretch()
        left_area_layout.addWidget(col0_widget, 1)

        col1_widget = QWidget()
        col1_layout = QVBoxLayout(col1_widget)
        col1_layout.setContentsMargins(0, 0, 0, 0)
        col1_layout.setSpacing(8)
        col1_layout.addStretch()

        station_row = QWidget()
        station_row_layout = QHBoxLayout(station_row)
        station_row_layout.setContentsMargins(0, 0, 0, 0)
        station_row_layout.setSpacing(8)

        self.station_label = QLabel("工站:")
        self.station_label.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        station_row_layout.addWidget(self.station_label)

        self.station_combo = QComboBox()
        stations = self.all_stations if self.all_stations else ["无工站"]
        self.station_combo.addItems(stations)
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
        self.station_combo.currentTextChanged.connect(self.on_station_changed)
        station_row_layout.addWidget(self.station_combo)
        station_row_layout.addStretch()
        col1_layout.addWidget(station_row)

        checkbox_container = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(16)

        self.checkbox_general = QCheckBox("通用操作")
        self.checkbox_general.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.checkbox_general.setStyleSheet("padding: 4px;")
        self.checkbox_general.stateChanged.connect(self.on_category_filter_changed)
        checkbox_layout.addWidget(self.checkbox_general)

        self.checkbox_product = QCheckBox("产品相关")
        self.checkbox_product.setFont(QFont("Microsoft YaHei", FONT_SIZE))
        self.checkbox_product.setStyleSheet("padding: 4px;")
        self.checkbox_product.stateChanged.connect(self.on_category_filter_changed)
        checkbox_layout.addWidget(self.checkbox_product)

        checkbox_layout.addStretch()
        col1_layout.addWidget(checkbox_container)
        col1_layout.addStretch()
        left_area_layout.addWidget(col1_widget, 1)

        layout.addWidget(self.top_left_area, 1)

        self.top_right_area = QWidget()
        right_layout = QVBoxLayout(self.top_right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addStretch()

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
        self.search_input.textChanged.connect(self.on_search_changed)
        right_layout.addWidget(self.search_input, alignment=Qt.AlignCenter)
        right_layout.addStretch()

        layout.addWidget(self.top_right_area, 1)
        return widget

    # ---------- 左侧面板 ----------
    def create_left_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.left_title = QLabel("📂 关联文件")
        self.left_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50; padding-bottom: 6px;")
        layout.addWidget(self.left_title)

        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Microsoft YaHei", 11))
        self.file_list.setStyleSheet("""
            QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #e0e0e0; }
            QListWidget::item:hover { background-color: #f0f7ff; }
        """)
        self.file_list.itemClicked.connect(self.on_file_clicked)
        layout.addWidget(self.file_list)
        return widget

    # ---------- 右侧查看模式 ----------
    def create_view_mode_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.right_title = QLabel("📢 工站动态推送")
        self.right_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50; padding-bottom: 6px;")
        layout.addWidget(self.right_title)

        self.push_browser = QTextBrowser()
        self.push_browser.setOpenExternalLinks(False)
        self.push_browser.anchorClicked.connect(self.on_anchor_clicked)
        self.push_browser.setStyleSheet("""
            font-size: 12pt; 
            line-height: 1.8; 
            background-color: #fafafa; 
            border: 1px solid #ddd; 
            border-radius: 4px;
        """)
        layout.addWidget(self.push_browser)
        return widget

    # ---------- 右侧考核模式 ----------
    def create_quiz_mode_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标题和分数（右上角大号分数）
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.quiz_title = QLabel("📝 考核模式 - 开卷答题")
        self.quiz_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #c0392b; padding: 8px 12px; background: #fef9e7; border-radius: 4px;")
        header_layout.addWidget(self.quiz_title)

        header_layout.addStretch()

        # 右上角分数显示（大字）
        self.quiz_score_label = QLabel("")
        self.quiz_score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.quiz_score_label.setStyleSheet("font-size: 36px; font-weight: bold; color: #2c3e50; padding: 4px 16px;")
        header_layout.addWidget(self.quiz_score_label)

        layout.addWidget(header_widget)

        # 滚动区域（题目）
        self.quiz_scroll = QScrollArea()
        self.quiz_scroll.setWidgetResizable(True)
        self.quiz_scroll.setStyleSheet("background: white; border: none;")
        self.quiz_container = QWidget()
        self.quiz_container.setStyleSheet("background: white;")
        self.quiz_layout = QVBoxLayout(self.quiz_container)
        self.quiz_layout.setContentsMargins(16, 16, 16, 16)
        self.quiz_layout.setSpacing(16)
        self.quiz_layout.addStretch()
        self.quiz_scroll.setWidget(self.quiz_container)
        layout.addWidget(self.quiz_scroll)

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
        self.open_pdf_btn.clicked.connect(self.on_quiz_open_pdf)
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
        self.restart_btn.clicked.connect(self.on_quiz_restart)
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
        self.save_btn.clicked.connect(self.on_quiz_save_answers)
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
        self.submit_btn.clicked.connect(self.submit_quiz)
        self.submit_btn.setEnabled(False)
        action_layout.addWidget(self.submit_btn, 1)

        layout.addLayout(action_layout)

        self.open_pdf_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        return widget

    # ---------- 同步与调整 ----------
    def sync_top_layout(self):
        if not hasattr(self, 'splitter'):
            return
        left_width = self.splitter.widget(0).width()
        right_width = self.splitter.widget(1).width()
        self.top_left_area.setFixedWidth(left_width)
        self.top_right_area.setFixedWidth(right_width)
        self.adjust_search_width()

    def adjust_search_width(self):
        if not hasattr(self, 'search_input') or not hasattr(self, 'top_right_area'):
            return
        container_width = self.top_right_area.width()
        if container_width <= 0:
            return
        target = int(container_width * 0.8)
        self.search_input.setMinimumWidth(target)
        self.search_input.setMaximumWidth(target)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.sync_top_layout)

    # ---------- 核心交互 ----------
    def toggle_login(self):
        if self.logged_in:
            self.logged_in = False
            self.current_user = ""
            self.user_label.setText("👤 未登录")
            self.user_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12pt;")
            self.login_btn.setText("登录")
            if self.exam_toggle.isChecked():
                self.exam_toggle.setChecked(False)
            self.refresh_left_list()
            self.update_right_panel()
            self.status_bar.showMessage("已退出")
        else:
            dialog = LoginDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                username = dialog.get_username()
                if username:
                    self.logged_in = True
                    self.current_user = username
                    self.user_label.setText(f"👤 {username} (已登录)")
                    self.user_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12pt;")
                    self.login_btn.setText("退出")
                    self.status_bar.showMessage(f"欢迎, {username}")
                    self.refresh_left_list()
                    self.update_right_panel()
                    if self.exam_toggle.isChecked():
                        self.exam_toggle.setChecked(False)

    def on_station_changed(self, station_name):
        if not self.logged_in:
            self.status_bar.showMessage("请先登录")
            return
        self.current_station = station_name
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.refresh_left_list()
        self.update_right_panel()
        self.status_bar.showMessage(f"切换到工站: {station_name}")

    def on_category_filter_changed(self):
        if not self.logged_in:
            return
        self.refresh_left_list()
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.update_right_panel()

    # ---------- PDF 打开 ----------
    def open_pdf_by_name(self, pdf_name, page=1, highlight_words=""):
        if not self.logged_in:
            QMessageBox.warning(self, "提示", "请先登录")
            return
        pdf_bytes = DATA_LOADER.get_pdf_bytes(pdf_name)
        if pdf_bytes is None:
            QMessageBox.warning(self, "提示", f"未找到PDF文件: {pdf_name}")
            return
        all_docs = self.knowledge_data.get("documents", [])
        doc_node = None
        for doc in all_docs:
            if doc.get("pdf_name", "") == pdf_name:
                doc_node = doc
                break
        try:
            viewer = PDFViewerDialog(
                pdf_bytes=pdf_bytes,
                pdf_name=pdf_name,
                initial_page=page,
                highlight_words=highlight_words,
                doc_node=doc_node,
                all_docs=all_docs,
                get_pdf_bytes_func=DATA_LOADER.get_pdf_bytes,
                parent=self
            )
            viewer.show()
            self.status_bar.showMessage(f"已打开: {pdf_name} (第{page}页)")
        except Exception as e:
            QMessageBox.critical(self, "PDF查看器错误", f"无法显示PDF：\n{str(e)}")

    def on_anchor_clicked(self, url):
        if url.scheme() == "openpdf":
            query = url.query()
            params = {}
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v
            pdf_name = params.get("file", "")
            page_str = params.get("page", "1")
            highlight = params.get("highlight", "")
            try:
                page = int(page_str)
            except ValueError:
                page = 1
            if pdf_name:
                self.open_pdf_by_name(pdf_name, page, highlight)
                self.search_input.blockSignals(True)
                self.search_input.clear()
                self.search_input.blockSignals(False)
                self.update_right_panel()

    def on_file_clicked(self, item):
        if not self.logged_in:
            QMessageBox.warning(self, "提示", "请先登录")
            return
        pdf_name = item.text()
        if "  " in pdf_name:
            pdf_name = pdf_name.split("  ")[0].strip()
        self._current_selected_pdf = pdf_name
        if self.exam_toggle.isChecked():
            self.load_quiz_for_pdf(pdf_name)
        else:
            self.open_pdf_by_name(pdf_name, 1, "")

    # ---------- 考核模式切换 ----------
    def on_exam_mode_toggled(self, checked):
        if checked and not self.logged_in:
            QMessageBox.warning(self, "提示", "请先登录才能进入考核模式")
            self.exam_toggle.setChecked(False)
            return
        if checked:
            self.exam_toggle.setText("📝 查看模式")
            self.right_stack.setCurrentIndex(1)
            self.search_input.hide()
            self.status_bar.showMessage("已进入考核模式")
            self.load_quiz_records()
            self.refresh_left_list()
            if self._current_selected_pdf:
                self.load_quiz_for_pdf(self._current_selected_pdf)
            else:
                self.clear_quiz()
                label = QLabel("请从左侧选择一个文件以加载题库。")
                label.setStyleSheet("color: #7f8c8d; font-size: 14px; padding: 16px;")
                self.quiz_layout.insertWidget(0, label)
                self.submit_btn.setEnabled(False)
        else:
            self.exam_toggle.setText("📝 考核模式")
            self.right_stack.setCurrentIndex(0)
            self.search_input.show()
            self.status_bar.showMessage("已退出考核模式")
            self.save_quiz_records()
            self.update_right_panel()
            self.refresh_left_list()

    # ---------- 考核模式操作 ----------
    def clear_quiz(self):
        while self.quiz_layout.count() > 1:
            item = self.quiz_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.quiz_score_label.setText("")
        self.quiz_questions = []
        self.quiz_answer_widgets = []

    def load_quiz_for_pdf(self, pdf_name):
        self.clear_quiz()
        self.open_pdf_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.submit_btn.setEnabled(False)

        normalized_name = pdf_name.strip()
        quiz_bank = DATA_LOADER.get_quiz_bank()
        quiz_info = quiz_bank.get(normalized_name)
        if quiz_info is None:
            for key in quiz_bank:
                if key.lower() == normalized_name.lower():
                    quiz_info = quiz_bank[key]
                    normalized_name = key
                    break

        if quiz_info is None:
            label = QLabel("该文档暂无题库。")
            label.setStyleSheet("color: #7f8c8d; font-size: 16px; padding: 16px;")
            self.quiz_layout.insertWidget(0, label)
            self.submit_btn.setEnabled(False)
            return

        if isinstance(quiz_info, list):
            questions = quiz_info
            version = "未知版本"
        else:
            questions = quiz_info.get("questions", [])
            version = quiz_info.get("version", "未知版本")

        if not questions:
            label = QLabel("该文档题库为空。")
            label.setStyleSheet("color: #7f8c8d; font-size: 16px; padding: 16px;")
            self.quiz_layout.insertWidget(0, label)
            self.submit_btn.setEnabled(False)
            return

        self.quiz_questions = questions
        self.quiz_pdf_name = normalized_name
        self.quiz_version = version

        # 从记录中获取数据
        record = self.quiz_records.get(normalized_name, {})
        score = record.get("score", 0)
        submitted = record.get("submitted", False)
        saved_answers = record.get("answers", [])

        # 右上角显示分数
        if score > 0:
            self.quiz_score_label.setText(f"{score}分")
            color = self._score_to_color(score)
            self.quiz_score_label.setStyleSheet(
                f"font-size: 36px; font-weight: bold; color: rgb({color[0]},{color[1]},{color[2]}); padding: 4px 16px;"
            )
        else:
            self.quiz_score_label.setText("")

        # 渲染题目，传递 submitted 和 correct_answers
        self.render_quiz(questions, submitted=submitted, saved_answers=saved_answers)

        # 恢复已保存的答案（如果未提交，恢复；如果已提交，则恢复但不可修改？但我们仍允许修改，重新提交会覆盖）
        if saved_answers and len(saved_answers) == len(self.quiz_answer_widgets):
            for idx, ans in enumerate(saved_answers):
                if not ans:
                    continue
                item = self.quiz_answer_widgets[idx]
                if item['type'] == 'single':
                    for i, btn in enumerate(item['widgets']):
                        if chr(65 + i) == ans:
                            btn.setChecked(True)
                            break
                else:
                    for i, btn in enumerate(item['widgets']):
                        btn.setChecked(chr(65 + i) in ans)

        self.submit_btn.setEnabled(True)
        self.open_pdf_btn.setEnabled(True)
        self.restart_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def render_quiz(self, questions, submitted=False, saved_answers=None):
        from PyQt5.QtWidgets import QGroupBox, QRadioButton, QCheckBox, QButtonGroup, QVBoxLayout, QLabel, QHBoxLayout

        self.quiz_answer_widgets.clear()

        option_labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        for idx, q in enumerate(questions):
            group_box = QGroupBox()
            group_box.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 8px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                    color: #1a3c6e;
                    font-size: 15px;
                }
            """)
            title = f"第 {idx+1} 题（{'单选' if q['type'] == 'single' else '多选'}）"
            group_box.setTitle(title)

            vbox = QVBoxLayout(group_box)
            vbox.setSpacing(10)

            # 题干
            question_label = QLabel(q['question'])
            question_label.setWordWrap(True)
            question_label.setStyleSheet("font-size: 24px; padding: 4px 0;")
            vbox.addWidget(question_label)

            # 选项
            option_widgets = []
            if q['type'] == 'single':
                btn_group = QButtonGroup()
                for i, opt_text in enumerate(q['options']):
                    label_text = f"{option_labels[i]}. {opt_text}" if i < len(option_labels) else opt_text
                    radio = QRadioButton(label_text)
                    radio.setStyleSheet("font-size: 22px; padding: 4px 0;")
                    vbox.addWidget(radio)
                    btn_group.addButton(radio, i)
                    option_widgets.append(radio)
                self.quiz_answer_widgets.append({
                    'type': 'single',
                    'group': btn_group,
                    'widgets': option_widgets,
                    'answer': q['answer']
                })
            else:
                for i, opt_text in enumerate(q['options']):
                    label_text = f"{option_labels[i]}. {opt_text}" if i < len(option_labels) else opt_text
                    checkbox = QCheckBox(label_text)
                    checkbox.setStyleSheet("font-size: 22px; padding: 4px 0;")
                    vbox.addWidget(checkbox)
                    option_widgets.append(checkbox)
                self.quiz_answer_widgets.append({
                    'type': 'multi',
                    'widgets': option_widgets,
                    'answer': q['answer']
                })

            # 如果已提交，显示正确答案和用户答案对比
            if submitted:
                correct_ans = q['answer']
                user_ans = saved_answers[idx] if saved_answers and idx < len(saved_answers) else "未选"
                # 判断对错
                is_correct = (user_ans == correct_ans)
                result_text = "✅ 正确" if is_correct else "❌ 错误"
                result_color = "#27ae60" if is_correct else "#e74c3c"
                correct_display = f"正确答案：{correct_ans}"
                user_display = f"您的答案：{user_ans if user_ans else '未选'}"
                result_label = QLabel(f"{result_text} | {correct_display} | {user_display}")
                result_label.setStyleSheet(f"font-size: 14px; color: {result_color}; padding: 4px; background: #f9f9f9; border-radius: 4px;")
                vbox.addWidget(result_label)

            self.quiz_layout.insertWidget(self.quiz_layout.count() - 1, group_box)

        if questions:
            tip_label = QLabel("请完成所有题目后点击「提交答案」")
            tip_label.setStyleSheet("color: #888; font-size: 14px; padding: 4px;")
            self.quiz_layout.insertWidget(self.quiz_layout.count() - 1, tip_label)

    # ---------- 按钮功能 ----------
    def on_quiz_open_pdf(self):
        if self.quiz_pdf_name:
            self.open_pdf_by_name(self.quiz_pdf_name, 1, "")
        else:
            QMessageBox.warning(self, "提示", "请先选择一个文档。")

    def on_quiz_restart(self):
        if not self.quiz_pdf_name:
            QMessageBox.warning(self, "提示", "请先选择一个文档。")
            return
        if self.quiz_pdf_name in self.quiz_records:
            record = self.quiz_records[self.quiz_pdf_name]
            record["answers"] = []
            record["score"] = 0
            record["submitted"] = False
            self.quiz_records[self.quiz_pdf_name] = record
            self.save_quiz_records()
        self.load_quiz_for_pdf(self.quiz_pdf_name)
        self.submit_btn.setEnabled(True)
        QMessageBox.information(self, "重新答题", "已重置答题状态。")

    def on_quiz_save_answers(self):
        if not self.quiz_pdf_name:
            QMessageBox.warning(self, "提示", "请先选择一个文档。")
            return

        answers = []
        for idx, item in enumerate(self.quiz_answer_widgets):
            if item['type'] == 'single':
                selected = item['group'].checkedButton()
                ans = chr(65 + item['group'].buttons().index(selected)) if selected else ""
            else:
                selected_indices = [i for i, cb in enumerate(item['widgets']) if cb.isChecked()]
                ans = ''.join(chr(65 + i) for i in sorted(selected_indices)) if selected_indices else ""
            answers.append(ans)

        record = self.quiz_records.get(self.quiz_pdf_name, {})
        record["version"] = self.quiz_version
        record["answers"] = answers
        # 不覆盖分数和提交状态
        self.quiz_records[self.quiz_pdf_name] = record
        self.save_quiz_records()

        QMessageBox.information(self, "保存答案", "答案已保存到记录文件。")

    # ---------- 记录文件管理 ----------
    def load_quiz_records(self):
        if not self.logged_in:
            return
        username = self.current_user if self.current_user else "admin"
        records_dir = Path("D:/SOP_helper")
        records_dir.mkdir(parents=True, exist_ok=True)
        self.records_file_path = records_dir / f"{username}.json"

        if not self.records_file_path.exists():
            self.quiz_records = {}
            self.save_quiz_records()
            return

        try:
            with open(self.records_file_path, "r", encoding="utf-8") as f:
                self.quiz_records = json.load(f)
        except Exception as e:
            self.quiz_records = {}
            self.save_quiz_records()
            return

        # 校验版本
        quiz_bank = DATA_LOADER.get_quiz_bank()
        updated = False
        for pdf_name in list(self.quiz_records.keys()):
            record = self.quiz_records[pdf_name]
            latest_version = quiz_bank.get(pdf_name, {}).get("version", "")
            if not latest_version or record.get("version") != latest_version:
                self.quiz_records[pdf_name] = {
                    "version": latest_version,
                    "answers": [],
                    "score": 0,
                    "submitted": False
                }
                updated = True

        if updated:
            self.save_quiz_records()

    def save_quiz_records(self):
        if not self.records_file_path:
            return
        try:
            with open(self.records_file_path, "w", encoding="utf-8") as f:
                json.dump(self.quiz_records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存答题记录失败: {e}")

    # ---------- 提交答案 ----------
    def submit_quiz(self):
        import openpyxl
        from datetime import datetime

        if not self.quiz_answer_widgets:
            return

        total = len(self.quiz_answer_widgets)
        correct = 0
        wrong_questions = []

        # 收集用户答案
        user_answers = []
        for idx, item in enumerate(self.quiz_answer_widgets):
            if item['type'] == 'single':
                selected = item['group'].checkedButton()
                ans = chr(65 + item['group'].buttons().index(selected)) if selected else ""
            else:
                selected_indices = [i for i, cb in enumerate(item['widgets']) if cb.isChecked()]
                ans = ''.join(chr(65 + i) for i in sorted(selected_indices)) if selected_indices else ""
            user_answers.append(ans)
            # 计算得分
            if ans == item['answer']:
                correct += 1
            else:
                if ans:  # 有答案但错误
                    wrong_questions.append(str(idx + 1))
                else:    # 未选
                    wrong_questions.append(str(idx + 1))

        score_percent = int(correct / total * 100) if total > 0 else 0
        score_str = f"{correct}/{total}"

        if self.quiz_pdf_name:
            record = self.quiz_records.get(self.quiz_pdf_name, {})
            record["version"] = self.quiz_version
            record["answers"] = user_answers
            record["score"] = score_percent
            record["submitted"] = True
            record["timestamp"] = datetime.now().isoformat()
            self.quiz_records[self.quiz_pdf_name] = record
            self.save_quiz_records()
            self.save_quiz_record(self.current_user, self.quiz_pdf_name, self.quiz_version, score_str, wrong_questions)

        # 显示得分并刷新界面
        self.quiz_score_label.setText(f"{score_percent}分")
        color = self._score_to_color(score_percent)
        self.quiz_score_label.setStyleSheet(
            f"font-size: 36px; font-weight: bold; color: rgb({color[0]},{color[1]},{color[2]}); padding: 4px 16px;"
        )
        self.submit_btn.setEnabled(False)
        # 重新加载题库以显示正确答案
        if self.quiz_pdf_name:
            self.load_quiz_for_pdf(self.quiz_pdf_name)
        self.refresh_left_list()

    def save_quiz_record(self, user, quiz_name, version, score, wrong_questions):
        import openpyxl
        from datetime import datetime
        from pathlib import Path

        excel_path = Path("assets/personnel_data.xlsx")
        excel_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if excel_path.exists():
                wb = openpyxl.load_workbook(excel_path)
                ws = wb.active
            else:
                wb = openpyxl.Workbook()
                ws = wb.active
                headers = ["人员", "题库名", "版本", "得分", "错题", "时间"]
                for col, header in enumerate(headers, 1):
                    ws.cell(row=1, column=col, value=header)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_num = ws.max_row + 1
            ws.cell(row=row_num, column=1, value=user)
            ws.cell(row=row_num, column=2, value=quiz_name)
            ws.cell(row=row_num, column=3, value=version)
            ws.cell(row=row_num, column=4, value=score)
            ws.cell(row=row_num, column=5, value=", ".join(wrong_questions) if wrong_questions else "无")
            ws.cell(row=row_num, column=6, value=now)

            wb.save(excel_path)
        except Exception as e:
            print(f"保存考核记录失败: {e}")

    # ---------- 颜色渐变辅助 ----------
    def _score_to_color(self, score):
        score = max(0, min(100, score))
        if score <= 50:
            ratio = score / 50.0
            r = 255
            g = int(255 * ratio)
            b = 0
        else:
            ratio = (score - 50) / 50.0
            r = int(255 * (1 - ratio))
            g = 255
            b = 0
        return r, g, b

    # ---------- 搜索相关 ----------
    def on_search_changed(self, text):
        if not self.logged_in:
            return
        if not text.strip():
            self.update_right_panel()
            return
        if not self.search_index:
            self.build_dynamic_index()
        results = self._keyword_search(text, self.search_index)
        self.current_results = results
        self.display_search_results(results, text)

    def build_dynamic_index(self):
        pdf_list = self.station_to_pdfs.get(self.current_station, [])
        show_general = self.checkbox_general.isChecked()
        show_product = self.checkbox_product.isChecked()
        if show_general or show_product:
            filtered = []
            for pdf_name in pdf_list:
                category = self.file_categories.get(pdf_name, "")
                if show_general and category == "通用操作":
                    filtered.append(pdf_name)
                elif show_product and category == "产品相关":
                    filtered.append(pdf_name)
            pdf_list = filtered

        docs = self.knowledge_data.get("documents", [])
        pdf_name_set = set(pdf_list)
        matched_docs = [doc for doc in docs if doc.get("pdf_name", "") in pdf_name_set]
        self.search_index = self._build_flat_index(matched_docs)
        return self.search_index

    def _build_flat_index(self, documents):
        index = []
        seen = set()
        for doc in documents:
            doc_code = doc.get("doc_code", "")
            doc_name = doc.get("doc_name", "")
            pdf_name = doc.get("pdf_name", "")
            for proc in doc.get("processes", []):
                process_name = proc.get("name", "")
                pdf_page = proc.get("page", "N/A")
                content_items = proc.get("content", [])
                if not content_items:
                    continue
                if isinstance(content_items, list):
                    for item in content_items:
                        if isinstance(item, dict):
                            step_item = item.get("item_name", "")
                            content = item.get("content", "")
                            precautions = item.get("precautions", "")
                            key = (doc_code, process_name, step_item, content, precautions)
                            if key in seen:
                                continue
                            seen.add(key)
                            index.append({
                                "doc_code": doc_code,
                                "doc_name": doc_name,
                                "pdf_name": pdf_name,
                                "process_name": process_name,
                                "step_item": step_item,
                                "content": content,
                                "precautions": precautions,
                                "pdf_page": pdf_page,
                            })
                        elif isinstance(item, str):
                            key = (doc_code, process_name, "", item, "")
                            if key in seen:
                                continue
                            seen.add(key)
                            index.append({
                                "doc_code": doc_code,
                                "doc_name": doc_name,
                                "pdf_name": pdf_name,
                                "process_name": process_name,
                                "step_item": "",
                                "content": item,
                                "precautions": "",
                                "pdf_page": pdf_page,
                            })
                elif isinstance(content_items, dict):
                    pass
        return index

    def _keyword_search(self, query, index):
        if not query.strip() or not index:
            return []
        words = [w.strip() for w in re.split(r'[，,、。.；;：:！!？? \t\n\r]+', query) if w.strip()]
        if not words:
            return []
        results = []
        for record in index:
            score = 0
            matched_words = []
            doc_code_lower = record["doc_code"].lower()
            doc_name_lower = record["doc_name"].lower()
            process_name_lower = record["process_name"].lower()
            step_item_lower = record["step_item"].lower()
            content_lower = record["content"].lower()
            precautions_lower = record["precautions"].lower()
            for word in words:
                word_lower = word.lower()
                weight_boost = 1.5 if word.isdigit() else 1.0
                if word_lower in doc_code_lower:
                    score += int(20 * weight_boost)
                    matched_words.append(word)
                if word_lower in doc_name_lower:
                    score += int(15 * weight_boost)
                    matched_words.append(word)
                if word_lower in process_name_lower:
                    score += int(12 * weight_boost)
                    matched_words.append(word)
                if word_lower in step_item_lower:
                    score += int(10 * weight_boost)
                    matched_words.append(word)
                if word_lower in content_lower:
                    count = content_lower.count(word_lower)
                    score += int(3 * count * weight_boost)
                    matched_words.append(word)
                if word_lower in precautions_lower:
                    count = precautions_lower.count(word_lower)
                    score += int(2 * count * weight_boost)
                    matched_words.append(word)
            if score > 0:
                match_ratio = len(set(matched_words)) / len(words) if words else 0
                results.append({
                    "record": record,
                    "score": score,
                    "match_ratio": match_ratio,
                    "matched_words": list(set(matched_words)),
                })
        results.sort(key=lambda x: (x["score"], x["match_ratio"]), reverse=True)
        return [r["record"] for r in results[:30]]

    def display_search_results(self, results, query):
        if not results:
            self.push_browser.setHtml("<p style='color:#7f8c8d; font-size: 12pt;'>😅 未找到相关内容，请尝试其他关键词</p>")
            return
        groups = {}
        for item in results:
            pdf_name = item.get('pdf_name', '')
            key = (item['doc_name'], item['process_name'], item.get('pdf_page', 'N/A'), pdf_name)
            if key not in groups:
                groups[key] = {
                    'doc_name': item['doc_name'],
                    'process_name': item['process_name'],
                    'pdf_page': item.get('pdf_page', 'N/A'),
                    'pdf_name': pdf_name,
                    'items': []
                }
            groups[key]['items'].append({
                'step_item': item.get('step_item', ''),
                'content': item.get('content', ''),
                'precautions': item.get('precautions', '')
            })
        html_parts = [f"<h3>🔍 搜索结果: “{query}”</h3>"]
        html_parts.append(f"<p style='color:#666;'>共 {len(results)} 条匹配记录</p><hr>")
        for idx, (key, group) in enumerate(groups.items(), 1):
            html_parts.append(f"<h4 style='color:#1a3c6e;'>【{idx}】📂 {group['doc_name']}</h4>")
            if group['process_name']:
                html_parts.append(f"<p style='color:#555;'>→ {group['process_name']}</p>")
            page = group['pdf_page']
            pdf_name = group['pdf_name']
            link = f'<a href="openpdf://open?file={pdf_name}&page={page}&highlight={query}">📂 跳转</a>'
            html_parts.append(f"<p style='color:#888;'>📍 页码: {page}  {link}</p>")
            for item in group['items']:
                if item['step_item']:
                    html_parts.append(f"<p style='color:#0b5394; font-weight:bold;'>📌 {item['step_item']}</p>")
                if item['content']:
                    content = item['content']
                    for word in query.split():
                        content = content.replace(word, f"<span style='background-color:#ffeb3b;'>{word}</span>")
                    html_parts.append(f"<p style='margin-left:20px;'>{content}</p>")
                if item['precautions']:
                    html_parts.append(f"<p style='margin-left:20px; color:#d45c00;'>⚠️ 注意事项: {item['precautions']}</p>")
            html_parts.append("<hr>")
        self.push_browser.setHtml("".join(html_parts))

    # ---------- 辅助刷新 ----------
    def refresh_left_list(self):
        self.file_list.clear()
        if not self.logged_in:
            self.file_list.addItem("请先登录以查看文件")
            return

        pdf_list = self.station_to_pdfs.get(self.current_station, [])
        show_general = self.checkbox_general.isChecked()
        show_product = self.checkbox_product.isChecked()
        if show_general or show_product:
            filtered = []
            for pdf_name in pdf_list:
                category = self.file_categories.get(pdf_name, "")
                if show_general and category == "通用操作":
                    filtered.append(pdf_name)
                elif show_product and category == "产品相关":
                    filtered.append(pdf_name)
            pdf_list = filtered

        search_text = self.search_input.text().strip()
        if search_text:
            pdf_list = [p for p in pdf_list if search_text.lower() in p.lower()]

        is_quiz_mode = self.exam_toggle.isChecked()
        available_quiz_names = DATA_LOADER.get_available_quiz_names() if is_quiz_mode else []

        for pdf_name in pdf_list:
            if is_quiz_mode:
                if pdf_name not in available_quiz_names:
                    continue

            item = QListWidgetItem(pdf_name)

            if is_quiz_mode:
                record = self.quiz_records.get(pdf_name, {})
                score = record.get("score", 0)
                if score > 0:
                    color = self._score_to_color(score)
                    item.setForeground(QColor(color[0], color[1], color[2]))
                    item.setText(f"{pdf_name}  {score}分")
                else:
                    item.setForeground(Qt.red)
            else:
                if pdf_name in self.pdf_to_doc:
                    item.setForeground(Qt.green)
                else:
                    item.setForeground(Qt.red)

            self.file_list.addItem(item)

        if self.file_list.count() == 0:
            self.file_list.addItem("(暂无匹配的SOP文件)")

        self.build_dynamic_index()

    def update_right_panel(self):
        if not self.logged_in:
            self.push_browser.setHtml("<p style='color:#7f8c8d; font-size: 14pt;'>请先登录以查看工站更新推送。</p>")
            return
        pdf_list = self.station_to_pdfs.get(self.current_station, [])
        show_general = self.checkbox_general.isChecked()
        show_product = self.checkbox_product.isChecked()
        if show_general or show_product:
            filtered = []
            for pdf_name in pdf_list:
                category = self.file_categories.get(pdf_name, "")
                if show_general and category == "通用操作":
                    filtered.append(pdf_name)
                elif show_product and category == "产品相关":
                    filtered.append(pdf_name)
            pdf_list = filtered

        all_docs = self.knowledge_data.get("documents", [])
        doc_map = {doc.get("pdf_name", ""): doc for doc in all_docs}
        updates = []
        for pdf_name in pdf_list:
            doc = doc_map.get(pdf_name)
            if not doc:
                continue
            history_node = None
            history_page = "1"
            for proc in doc.get("processes", []):
                if proc.get("name") == "履历":
                    history_node = proc
                    history_page = proc.get("page", "1")
                    break
            if not history_node:
                continue
            history_list = history_node.get("content", [])
            if not history_list:
                continue
            latest = history_list[-1] if history_list else None
            if not latest:
                continue
            doc_name = doc.get("doc_name", pdf_name)
            revision_date = latest.get("revision_date", "")
            revision_content = latest.get("revision_content", "")
            version = latest.get("version", "")
            if len(revision_content) > 80:
                revision_content = revision_content[:80] + "..."
            updates.append({
                "pdf_name": pdf_name,
                "doc_name": doc_name,
                "date": revision_date,
                "content": revision_content,
                "version": version,
                "page": history_page
            })
        if not updates:
            self.push_browser.setHtml(f"<p style='color:#7f8c8d; font-size: 14pt;'>当前工站 <b>{self.current_station}</b> 暂无文档更新记录。</p>")
            return
        try:
            updates.sort(key=lambda x: x['date'], reverse=True)
        except:
            pass
        html_parts = [f"<div style='font-family: Microsoft YaHei, sans-serif;'>",
                      f"<h2 style='color: #2c3e50; margin-bottom: 15px;'>📢 {self.current_station} 动态推送</h2>",
                      "<div style='display: flex; flex-direction: column; gap: 14px;'>"]
        for update in updates:
            pdf_name = update['pdf_name']
            page = update['page']
            highlight = update['date']
            link = f'openpdf://open?file={pdf_name}&page={page}&highlight={highlight}'
            html_parts.append(f"""
            <div style='background: #ffffff; border-left: 4px solid #3498db; border-radius: 8px; padding: 14px 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.12); transition: box-shadow 0.2s; margin-bottom: 4px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 14pt; font-weight: bold; color: #1a3c6e;'>
                        📄 {update['doc_name']}
                        <span style='font-size: 12pt; font-weight: normal; color: #888; margin-left: 8px;'>
                            [{update.get('version', '')}]
                        </span>
                    </span>
                    <a href='{link}' style='color: #0066cc; text-decoration: underline; font-size: 11pt; cursor: pointer; background: transparent; padding: 0;'>跳转</a>
                </div>
                <div style='margin-top: 6px; font-size: 13pt; color: #555;'>📅 {update['date']}</div>
                <div style='margin-top: 4px; font-size: 13pt; color: #333; line-height: 1.5;'>{update['content']}</div>
            </div>
            """)
        html_parts.append("</div></div>")
        self.push_browser.setHtml("".join(html_parts))

    # ---------- 其他功能 ----------
    def create_icon(self):
        from PyQt5.QtCore import QRect, QSize, Qt
        size = 256
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        gradient = QRadialGradient(size/2, size/2, size/2)
        gradient.setColorAt(0, QColor(52, 152, 219))
        gradient.setColorAt(1, QColor(26, 82, 118))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 20, 20)
        painter.setPen(Qt.NoPen)
        shadow_color = QColor(0, 0, 0, 80)
        painter.setBrush(QBrush(shadow_color))
        painter.drawRoundedRect(6, 8, size-12, size-12, 18, 18)
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(4, 4, size-8, size-8, 16, 16)
        font = QFont("Arial", 48, QFont.Bold)
        font.setStyleHint(QFont.SansSerif)
        painter.setFont(font)
        painter.setPen(QPen(QColor(26, 82, 118), 2))
        rect = QRect(0, 0, size, size)
        painter.drawText(rect, Qt.AlignCenter, "SOP")
        painter.setPen(QPen(QColor(52, 152, 219, 180), 3))
        painter.drawLine(30, 90, 90, 30)
        painter.end()
        return QIcon(pixmap)

    def update_version_label(self):
        version = DATA_LOADER.get_current_version()
        self.version_label.setText(f"Version: {version}" if version else "Version: 开发模式")

    def check_data_update(self, show_no_update=False):
        # 数据版本更新
        if DATA_LOADER.check_update():
            self.knowledge_data = DATA_LOADER.get_knowledge_graph()
            self.station_to_pdfs = DATA_LOADER.get_station_to_pdfs()
            self.file_categories = DATA_LOADER.get_file_categories()
            self.all_stations = DATA_LOADER.get_all_stations()
            docs = self.knowledge_data.get("documents", [])
            self.pdf_to_doc = {doc.get("pdf_name", ""): True for doc in docs if doc.get("pdf_name")}
            self.refresh_left_list()
            self.update_right_panel()
            new_version = DATA_LOADER.get_current_version()
            self.status_bar.showMessage(f"数据已更新至版本 {new_version}")
            self.update_version_label()
            if show_no_update:
                QMessageBox.information(self, "提示", f"数据已更新至版本 {new_version}！")
        else:
            if show_no_update:
                QMessageBox.information(self, "提示", "当前已是最新版本。")

        # 有效期检查（新增）
        from app.core.license_validator import LicenseValidator
        if LicenseValidator.is_expired():
            LicenseValidator.prompt_for_license(parent=self)
            # 更新后刷新状态栏
            self.status_bar.showMessage("授权码验证通过，已延期。")
            
    def on_refresh_clicked(self):
        """手动点击刷新按钮，检查更新（有更新才刷新，无更新提示）"""
        self.check_data_update(show_no_update=True)