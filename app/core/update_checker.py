# app/core/update_checker.py
from PyQt5.QtWidgets import QMessageBox
from app.core.license_validator import LicenseValidator
from app.core.cloud_sync import sync_cloud


class UpdateChecker:
    """数据版本和有效期检查（基于云端同步）"""
    def __init__(self, parent, software_version):
        self.parent = parent
        self.software_version = software_version

    def check_data_update(self, show_no_update=False, silent=True):
        """
        执行完整的云同步，并根据结果刷新界面。
        :param show_no_update: 无更新时是否弹窗（仅手动触发时使用）
        :param silent: 是否静默（不弹窗、不显示进度）
        """
        ok, msg = sync_cloud(self.software_version, silent=silent)
        if ok:
            # 同步成功，通知主窗口刷新界面
            if hasattr(self.parent, 'refresh_after_sync'):
                self.parent.refresh_after_sync()
            else:
                # 降级处理（一般不会执行到）
                from app.core.data_loader import DATA_LOADER
                self.parent.knowledge_data = DATA_LOADER.get_knowledge_graph()
                self.parent.station_to_pdfs = DATA_LOADER.get_station_to_pdfs()
                self.parent.file_categories = DATA_LOADER.get_file_categories()
                self.parent.all_stations = DATA_LOADER.get_all_stations()
                docs = self.parent.knowledge_data.get("documents", [])
                self.parent.pdf_to_doc = {doc.get("pdf_name", ""): True for doc in docs if doc.get("pdf_name")}
                self.parent.refresh_left_list()
                self.parent.update_right_panel()
                self.parent.update_version_label()

            if not silent:
                if show_no_update:
                    QMessageBox.information(self.parent, "提示", "数据已同步至最新版本。")
                else:
                    self.parent.statusBar().showMessage("数据同步完成")
        else:
            # 同步失败（msg 包含错误描述）
            if not silent:
                # sync_cloud 内部已经弹出错误对话框（因为 silent=False），这里不再重复
                pass
            else:
                self.parent.statusBar().showMessage(f"同步失败: {msg}")

        # 授权检查（只在非静默时弹窗，避免打扰）
        if LicenseValidator.is_expired():
            if not silent:
                LicenseValidator.prompt_for_license(parent=self.parent)
                self.parent.statusBar().showMessage("授权码验证通过，已延期。")
            else:
                # 静默时不弹窗，可记录或忽略
                pass