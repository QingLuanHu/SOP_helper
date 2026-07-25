import os
import fitz  # PyMuPDF
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QSplitter, QListWidget,
    QListWidgetItem, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont


class ClickableLabel(QLabel):
    """可点击的标签，用于获取鼠标点击位置"""
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: white;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.viewer.on_label_clicked(event.pos().x(), event.pos().y())
        super().mousePressEvent(event)


class JumpReferenceDialog(QDialog):
    """选择跳转引用的对话框（一次关闭）"""
    def __init__(self, doc_name, sops, forms, parent=None):
        super().__init__(parent)
        self.setWindowTitle("跳转引用")
        self.resize(450, 350)
        self.setModal(True)
        self.selected_ref = None

        layout = QVBoxLayout(self)

        label = QLabel(f"文档：{doc_name}")
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        layout.addWidget(label)

        layout.addWidget(QLabel("请选择要跳转的引用："))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        for sop in sops:
            item = QListWidgetItem(f"📄 {sop.get('name', '')}")
            item.setData(Qt.UserRole, ("SOP", sop))
            self.list_widget.addItem(item)
        for form in forms:
            item = QListWidgetItem(f"📋 {form.get('name', '')}")
            item.setData(Qt.UserRole, ("FORM", form))
            self.list_widget.addItem(item)

        if self.list_widget.count() == 0:
            item = QListWidgetItem("（无相关引用）")
            item.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.jump_btn = QPushButton("跳转")
        self.jump_btn.setEnabled(False)
        self.jump_btn.clicked.connect(self.on_jump)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(lambda: self.done(QDialog.Rejected))
        btn_layout.addStretch()
        btn_layout.addWidget(self.jump_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        selected = self.list_widget.selectedItems()
        self.jump_btn.setEnabled(len(selected) > 0)

    def on_jump(self):
        selected = self.list_widget.selectedItems()
        if selected:
            self.selected_ref = selected[0].data(Qt.UserRole)
        self.done(QDialog.Accepted)

    def closeEvent(self, event):
        self.done(QDialog.Rejected)
        event.accept()


class PDFViewerDialog(QDialog):
    _open_count = 0
    MAX_WINDOWS = 20

    def __init__(self, pdf_bytes, pdf_name, initial_page=1,
                 highlight_words="", doc_node=None, all_docs=None,
                 get_pdf_bytes_func=None, parent=None):
        if PDFViewerDialog._open_count >= PDFViewerDialog.MAX_WINDOWS:
            QMessageBox.warning(
                parent,
                "提示",
                f"已打开 {PDFViewerDialog.MAX_WINDOWS} 个窗口，请关闭一些后再尝试。"
            )
            super().__init__(parent)
            self.setWindowTitle(pdf_name)
            self.resize(1100, 800)
            self.deleteLater()
            return

        super().__init__(parent)
        self.setWindowTitle(f"📄 {pdf_name}")
        self.resize(1100, 800)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)

        PDFViewerDialog._open_count += 1

        self.pdf_bytes = pdf_bytes
        self.pdf_name = pdf_name
        self.current_page = max(1, initial_page)
        self.scale_factor = 1.0
        self.doc = None
        self.total_pages = 0
        self.fit_width_mode = False
        self.zoom_mode = None

        # 存储高亮关键词
        self.highlight_words = highlight_words

        # 文档数据
        self.doc_node = doc_node
        self.all_docs = all_docs if all_docs else []
        self.get_pdf_bytes_func = get_pdf_bytes_func

        if self.doc_node:
            self.processes = self.doc_node.get("processes", [])
            self.global_sops = self.doc_node.get("related_sops", [])
            self.global_forms = self.doc_node.get("related_forms", [])
        else:
            self.processes = []
            self.global_sops = []
            self.global_forms = []

        self.main_layout = QVBoxLayout(self)

        self.toolbar = self.create_toolbar()
        self.toolbar.setFixedHeight(96)
        self.main_layout.addWidget(self.toolbar)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("目录")
        self.tree_widget.setFont(QFont("Microsoft YaHei", 10))
        self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)
        self.tree_widget.setMinimumWidth(150)
        self.tree_widget.setMaximumWidth(400)
        self.populate_tree()
        self.splitter.addWidget(self.tree_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("background: white;")
        self.image_label = ClickableLabel(self)
        self.scroll_area.setWidget(self.image_label)
        self.splitter.addWidget(self.scroll_area)

        self.splitter.setSizes([200, 900])
        self.main_layout.addWidget(self.splitter)

        self.load_pdf()
        self.render_page(self.current_page)
        QTimer.singleShot(100, self.delayed_fit_width)

        self.update_jump_btn_state()

    def create_toolbar(self):
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        self.toggle_tree_btn = QPushButton("目录")
        self.toggle_tree_btn.setFixedSize(50, 28)
        self.toggle_tree_btn.setToolTip("展开/折叠目录")
        self.toggle_tree_btn.clicked.connect(self.toggle_tree)
        layout.addWidget(self.toggle_tree_btn)

        self.jump_ref_btn = QPushButton("跳转引用")
        self.jump_ref_btn.setFixedSize(80, 28)
        self.jump_ref_btn.setToolTip("跳转到该文档的相关SOP或表单")
        self.jump_ref_btn.setEnabled(False)
        self.jump_ref_btn.clicked.connect(self.on_jump_reference)
        layout.addWidget(self.jump_ref_btn)

        self.page_label = QLabel("页码:")
        self.page_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(self.page_label)

        self.page_edit = QLineEdit()
        self.page_edit.setFixedWidth(60)
        self.page_edit.setAlignment(Qt.AlignCenter)
        self.page_edit.setFont(QFont("Microsoft YaHei", 9))
        self.page_edit.returnPressed.connect(self.go_to_page)
        layout.addWidget(self.page_edit)

        self.total_label = QLabel("/ 0")
        self.total_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(self.total_label)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(30, 26)
        self.prev_btn.clicked.connect(self.prev_page)
        layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(30, 26)
        self.next_btn.clicked.connect(self.next_page)
        layout.addWidget(self.next_btn)

        layout.addWidget(QLabel("缩放:"))
        self.zoom_edit = QLineEdit()
        self.zoom_edit.setFixedWidth(60)
        self.zoom_edit.setAlignment(Qt.AlignCenter)
        self.zoom_edit.setFont(QFont("Microsoft YaHei", 9))
        self.zoom_edit.setText("100%")
        self.zoom_edit.returnPressed.connect(self.apply_zoom)
        layout.addWidget(self.zoom_edit)

        self.zoom_btn = QPushButton("应用")
        self.zoom_btn.setFixedHeight(26)
        self.zoom_btn.clicked.connect(self.apply_zoom)
        layout.addWidget(self.zoom_btn)

        self.actual_btn = QPushButton("实际大小")
        self.actual_btn.setFixedHeight(26)
        self.actual_btn.clicked.connect(self.reset_zoom)
        layout.addWidget(self.actual_btn)

        self.fit_btn = QPushButton("适应宽度")
        self.fit_btn.setCheckable(True)
        self.fit_btn.setFixedHeight(26)
        self.fit_btn.clicked.connect(self.toggle_fit_width)
        layout.addWidget(self.fit_btn)

        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.setCheckable(True)
        self.zoom_in_btn.setFixedHeight(26)
        self.zoom_in_btn.clicked.connect(self.toggle_zoom_in)
        layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("🔍−")
        self.zoom_out_btn.setCheckable(True)
        self.zoom_out_btn.setFixedHeight(26)
        self.zoom_out_btn.clicked.connect(self.toggle_zoom_out)
        layout.addWidget(self.zoom_out_btn)

        layout.addStretch()
        return toolbar

    def update_jump_btn_state(self):
        has_refs = bool(self.global_sops or self.global_forms)
        self.jump_ref_btn.setEnabled(has_refs)

    def on_jump_reference(self):
        if PDFViewerDialog._open_count >= PDFViewerDialog.MAX_WINDOWS:
            QMessageBox.warning(
                self,
                "提示",
                f"已打开 {PDFViewerDialog.MAX_WINDOWS} 个窗口，请关闭一些后再尝试。"
            )
            return

        doc_name = self.doc_node.get("doc_name", "当前文档") if self.doc_node else "当前文档"
        dialog = JumpReferenceDialog(doc_name, self.global_sops, self.global_forms, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            ref = dialog.selected_ref
            if ref:
                ref_type, ref_data = ref
                target_name = ref_data.get("name", "")
                target_code = ref_data.get("code", "")

                found_doc = None
                for doc in self.all_docs:
                    if doc.get("doc_name", "") == target_name:
                        found_doc = doc
                        break

                if found_doc:
                    pdf_name = found_doc.get("pdf_name", "")
                    if self.get_pdf_bytes_func:
                        pdf_bytes = self.get_pdf_bytes_func(pdf_name)
                        if pdf_bytes:
                            new_viewer = PDFViewerDialog(
                                pdf_bytes=pdf_bytes,
                                pdf_name=pdf_name,
                                initial_page=1,
                                highlight_words="",  # 跳转引用时不传递高亮
                                doc_node=found_doc,
                                all_docs=self.all_docs,
                                get_pdf_bytes_func=self.get_pdf_bytes_func,
                                parent=self.parent()
                            )
                            new_viewer.show()
                        else:
                            QMessageBox.warning(self, "错误", f"无法获取PDF文件: {pdf_name}")
                    else:
                        QMessageBox.warning(self, "错误", "缺少PDF获取函数")
                else:
                    QMessageBox.warning(
                        self,
                        "未找到",
                        f"未找到名称匹配的文档：{target_name}\n（编号：{target_code}）"
                    )

    # ---------- 目录树 ----------
    def populate_tree(self):
        self.tree_widget.clear()
        if not self.processes:
            item = QTreeWidgetItem(["（无目录）"])
            self.tree_widget.addTopLevelItem(item)
            return

        def get_page_value(proc):
            page_str = proc.get("page", "0")
            try:
                return int(page_str)
            except (ValueError, TypeError):
                return 9999

        sorted_processes = sorted(self.processes, key=get_page_value)

        for proc in sorted_processes:
            name = proc.get("name", "未命名工序")
            page = proc.get("page", "N/A")
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.UserRole, page)
            self.tree_widget.addTopLevelItem(item)

        self.tree_widget.expandAll()

    def on_tree_item_clicked(self, item, column):
        page_data = item.data(0, Qt.UserRole)
        try:
            page = int(page_data)
            if 1 <= page <= self.total_pages:
                self.go_to_page(page)
            else:
                QMessageBox.warning(self, "提示", f"无效页码: {page_data}")
        except (ValueError, TypeError):
            QMessageBox.warning(self, "提示", f"无效页码: {page_data}")

    # ---------- 折叠/展开 ----------
    def toggle_tree(self):
        if self.tree_widget.isVisible():
            self.tree_widget.hide()
            sizes = self.splitter.sizes()
            sizes[0] = 0
            self.splitter.setSizes(sizes)
        else:
            self.tree_widget.show()
            sizes = self.splitter.sizes()
            sizes[0] = 200
            self.splitter.setSizes(sizes)

    # ---------- 加载PDF ----------
    def load_pdf(self):
        try:
            self.doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
            self.total_pages = len(self.doc)
            self.total_label.setText(f"/ {self.total_pages}")
            self.page_edit.setPlaceholderText(str(self.current_page))
            self.update_buttons()
        except Exception as e:
            QMessageBox.critical(self, "PDF加载错误", f"无法加载 PDF：\n{str(e)}")
            self.close()

    # ---------- 渲染页面（支持高亮） ----------
    def render_page(self, page_num):
        if not self.doc or page_num < 1 or page_num > self.total_pages:
            return

        self.current_page = page_num
        self.page_edit.setText(str(page_num))
        self.page_edit.setPlaceholderText(str(page_num))

        page = self.doc[page_num - 1]

        # ---- 清除旧高亮并添加新高亮（兼容旧版 PyMuPDF） ----
        if self.highlight_words:
            try:
                # 1. 清除该页所有已有的高亮注释
                annots = page.annots()
                if annots:
                    for annot in annots:
                        # 高亮注释类型为 8
                        if annot.type[0] == 8:
                            page.delete_annot(annot)

                # 2. 查找并高亮关键词
                words = self.highlight_words.split()
                for word in words:
                    if not word:
                        continue
                    rects = page.search_for(word)
                    for rect in rects:
                        # 使用 add_highlight_annot（兼容旧版本）
                        annot = page.add_highlight_annot(rect)
                        annot.set_colors(stroke=(1, 1, 0))  # 亮黄色
                        annot.update()
            except Exception as e:
                # 高亮失败时静默忽略，不影响 PDF 显示
                print(f"[高亮警告] {e}")

        # ---- 渲染页面 ----
        mat = fitz.Matrix(self.scale_factor, self.scale_factor)
        pix = page.get_pixmap(matrix=mat)

        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.width(), pixmap.height())

        self.setWindowTitle(f"{self.windowTitle().split(' - ')[0]} - 第 {page_num}/{self.total_pages} 页")
        self.update_buttons()


    # ---------- 导航 ----------
    def go_to_page(self, page_num=None):
        if page_num is None:
            try:
                page_num = int(self.page_edit.text())
            except ValueError:
                QMessageBox.warning(self, "提示", "请输入有效数字")
                return
        if 1 <= page_num <= self.total_pages:
            self.render_page(page_num)
        else:
            QMessageBox.warning(self, "提示", f"页码范围 1~{self.total_pages}")

    def prev_page(self):
        if self.current_page > 1:
            self.render_page(self.current_page - 1)

    def next_page(self):
        if self.current_page < self.total_pages:
            self.render_page(self.current_page + 1)

    def update_buttons(self):
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

    # ---------- 缩放 ----------
    def apply_zoom(self):
        try:
            text = self.zoom_edit.text().strip().replace('%', '')
            new_scale = float(text) / 100.0
            if new_scale > 0:
                self.scale_factor = new_scale
                self.render_page(self.current_page)
                self.clear_zoom_mode()
                self.fit_btn.setChecked(False)
                self.fit_width_mode = False
            else:
                QMessageBox.warning(self, "提示", "缩放值必须大于0")
        except ValueError:
            QMessageBox.warning(self, "提示", "请输入有效的百分比数字，例如 150")

    def reset_zoom(self):
        self.scale_factor = 1.0
        self.zoom_edit.setText("100%")
        self.render_page(self.current_page)
        self.clear_zoom_mode()
        self.fit_btn.setChecked(False)
        self.fit_width_mode = False

    # ---------- 适应宽度 ----------
    def toggle_fit_width(self):
        if self.fit_btn.isChecked():
            self.fit_width_mode = True
            self.clear_zoom_mode()
            self.fit_width()
        else:
            self.fit_width_mode = False

    def fit_width(self):
        if not self.doc:
            return
        area_width = self.scroll_area.viewport().width() - 20
        if area_width <= 0:
            return
        page = self.doc[self.current_page - 1]
        orig_width = page.rect.width
        if orig_width <= 0:
            return
        new_scale = area_width / orig_width
        if new_scale < 0.1:
            new_scale = 0.1
        self.scale_factor = new_scale
        self.zoom_edit.setText(f"{int(new_scale * 100)}%")
        self.render_page(self.current_page)

    def delayed_fit_width(self):
        self.fit_btn.setChecked(True)
        self.fit_width_mode = True
        self.fit_width()

    # ---------- 缩放模式 ----------
    def toggle_zoom_in(self):
        if self.zoom_in_btn.isChecked():
            self.zoom_mode = 'in'
            self.zoom_out_btn.setChecked(False)
            self.fit_btn.setChecked(False)
            self.fit_width_mode = False
        else:
            self.zoom_mode = None

    def toggle_zoom_out(self):
        if self.zoom_out_btn.isChecked():
            self.zoom_mode = 'out'
            self.zoom_in_btn.setChecked(False)
            self.fit_btn.setChecked(False)
            self.fit_width_mode = False
        else:
            self.zoom_mode = None

    def clear_zoom_mode(self):
        self.zoom_mode = None
        self.zoom_in_btn.setChecked(False)
        self.zoom_out_btn.setChecked(False)

    # ---------- 点击缩放 ----------
    def on_label_clicked(self, x, y):
        if self.zoom_mode not in ('in', 'out'):
            return

        scale = self.scale_factor
        orig_x = x / scale
        orig_y = y / scale

        factor = 1.2 if self.zoom_mode == 'in' else 0.8
        new_scale = scale * factor
        if new_scale < 0.1:
            new_scale = 0.1
        if new_scale > 5.0:
            new_scale = 5.0

        self.scale_factor = new_scale
        self.zoom_edit.setText(f"{int(new_scale * 100)}%")
        self.render_page(self.current_page)

        new_x = orig_x * new_scale
        new_y = orig_y * new_scale

        view = self.scroll_area.viewport()
        view_width = view.width()
        view_height = view.height()
        self.scroll_area.ensureVisible(int(new_x - view_width/2), int(new_y - view_height/2), view_width//2, view_height//2)

    # ---------- 窗口事件 ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_width_mode:
            self.fit_width()

    def closeEvent(self, event):
        if self.doc:
            self.doc.close()
        if PDFViewerDialog._open_count > 0:
            PDFViewerDialog._open_count -= 1
        event.accept()