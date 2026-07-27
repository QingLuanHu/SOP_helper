from PyQt5.QtWidgets import QMessageBox
from app.core.license_validator import LicenseValidator


class UpdateChecker:
    """数据版本和有效期检查"""
    def __init__(self, parent):
        self.parent = parent

    def check_data_update(self, show_no_update=False):
        from app.core.data_loader import DATA_LOADER
        if DATA_LOADER.check_update():
            self.parent.knowledge_data = DATA_LOADER.get_knowledge_graph()
            self.parent.station_to_pdfs = DATA_LOADER.get_station_to_pdfs()
            self.parent.file_categories = DATA_LOADER.get_file_categories()
            self.parent.all_stations = DATA_LOADER.get_all_stations()
            docs = self.parent.knowledge_data.get("documents", [])
            self.parent.pdf_to_doc = {doc.get("pdf_name", ""): True for doc in docs if doc.get("pdf_name")}
            self.parent.refresh_left_list()
            self.parent.update_right_panel()
            new_version = DATA_LOADER.get_current_version()
            # ✅ 使用 statusBar() 方法
            self.parent.statusBar().showMessage(f"数据已更新至版本 {new_version}")
            self.parent.update_version_label()
            if show_no_update:
                QMessageBox.information(self.parent, "提示", f"数据已更新至版本 {new_version}！")
        else:
            if show_no_update:
                QMessageBox.information(self.parent, "提示", "当前已是最新版本。")

        # 有效期检查
        if LicenseValidator.is_expired():
            LicenseValidator.prompt_for_license(parent=self.parent)
            self.parent.statusBar().showMessage("授权码验证通过，已延期。")