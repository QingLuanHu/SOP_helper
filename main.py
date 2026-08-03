import sys
import traceback
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt, QTimer, QSharedMemory
from PyQt5.QtGui import QFont

from app.core.license_validator import LicenseValidator
from app.core.cloud_sync import check_and_sync, sync_cloud

# ========== 软件版本（可在此统一修改） ==========
SOFTWARE_VERSION = "2.0.2"

# ============================================================
# 授权检查
# ============================================================
def check_license():
    license_path = Path("C:/Program Files/SOP_helper/license")
    if not license_path.exists():
        return False
    try:
        content = license_path.read_text(encoding="utf-8").strip()
        return content == "HF796"
    except Exception:
        return False

def show_license_error():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("授权失败")
    msg.setText("许可证无效或已过期，请联系管理员。")
    msg.setInformativeText("软件将退出。")
    msg.exec_()
    sys.exit(1)

# ============================================================
# 单实例检测
# ============================================================
def check_single_instance():
    shared_memory = QSharedMemory("796796796")
    if shared_memory.attach():
        return False
    else:
        if shared_memory.create(1):
            app = QApplication.instance()
            app._single_shared_memory = shared_memory
            return True
        else:
            return False

# ============================================================
# 主程序入口
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # 1. 授权检查
    if not check_license():
        show_license_error()

    # 2. 有效期检查
    if LicenseValidator.is_expired():
        LicenseValidator.prompt_for_license()

    # 3. 单实例检测
    if not check_single_instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("提示")
        msg.setText("程序已在运行中，请勿重复打开。")
        msg.exec_()
        sys.exit(0)

    # 4. 云端同步（阻断式，此时单实例已确保）
    if not check_and_sync(SOFTWARE_VERSION, silent=False):
        sys.exit(1)

    # ---------- 加载进度弹窗 ----------
    progress = QProgressDialog("加载数据中，请稍候...", "取消", 0, 0, None)
    progress.setWindowTitle("工位SOP助手")
    progress.setWindowModality(Qt.WindowModal)
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.resize(400, 120)
    progress.setMinimumSize(350, 100)
    progress.show()
    app.processEvents()

    # ---------- 数据加载 ----------
    def load_data():
        try:
            from app.core.data_loader import DATA_LOADER
            _ = DATA_LOADER.get_knowledge_graph()
            _ = DATA_LOADER.get_all_pdf_names()
        except Exception as e:
            progress.close()
            traceback.print_exc()
            QMessageBox.critical(None, "加载失败", f"数据加载出错：\n{str(e)}")
            sys.exit(1)
        progress.close()

        try:
            from app.main_window import MainWindow
            window = MainWindow()
            window.show()
            window.raise_()
            window.activateWindow()
            app.main_window = window

            # 每小时静默检查更新
            timer = QTimer()
            timer.timeout.connect(lambda: sync_cloud(SOFTWARE_VERSION, silent=True))
            timer.start(60 * 60 * 1000)
            app._cloud_timer = timer

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(None, "启动失败", f"创建主窗口失败：\n{str(e)}")
            sys.exit(1)

    QTimer.singleShot(10, load_data)

    try:
        exit_code = app.exec_()
        if hasattr(app, '_single_shared_memory'):
            app._single_shared_memory.detach()
        sys.exit(exit_code)
    except Exception as e:
        print(f"[ERROR] 事件循环异常: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()