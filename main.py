import sys
import traceback
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt, QTimer, QSharedMemory
from PyQt5.QtGui import QFont

from app.core.license_validator import LicenseValidator
from app.core.cloud_sync import sync_cloud, sync_license_file, VERSION_FILE

# ========== 软件版本（与云端 version.json 的 SoftwareVersion 对应） ==========
SOFTWARE_VERSION = "2.0.2"


# ============================================================
# 固定 License 校验
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
# 软件版本校验（阻断式）
# ============================================================
def check_software_version() -> bool:
    if not VERSION_FILE.exists():
        QMessageBox.critical(None, "配置缺失", "未找到 assets/version.json 配置文件。")
        return False

    try:
        import json
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        remote_ver = manifest.get("SoftwareVersion", "")
        if remote_ver != SOFTWARE_VERSION:
            QMessageBox.critical(
                None,
                "版本错误",
                f"软件版本不匹配！\n当前程序版本：{SOFTWARE_VERSION}\n所需数据版本：{remote_ver}\n请更新软件。"
            )
            return False
        return True
    except Exception as e:
        QMessageBox.critical(None, "版本校验失败", f"读取 version.json 失败：{e}")
        return False


# ============================================================
# 主程序入口
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # ====== 1. 单实例检测 ======
    if not check_single_instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("提示")
        msg.setText("程序已在运行中，请勿重复打开。")
        msg.exec_()
        sys.exit(0)

    # ====== 2. 云同步（同步 version.json + 数据文件，返回 cloud_root） ======
    ok, cloud_root = sync_cloud(SOFTWARE_VERSION, silent=False)

    # ====== 3. 从云端复制 sequence.dat 覆盖本地（无痕续期） ======
    if cloud_root:
        sync_license_file(cloud_root)  # 静默执行

    # ====== 4. 软件版本校验（阻断式） ======
    if not check_software_version():
        sys.exit(1)

    # ====== 5. 授权检查 ======
    # 5a. 固定 License（可根据需要启用）
    if not check_license():
        show_license_error()

    # 5b. 有效期校验（此时 sequence.dat 已被云端最新覆盖）
    if LicenseValidator.is_expired():
        LicenseValidator.prompt_for_license()

    # ====== 6. 加载进度弹窗 ======
    progress = QProgressDialog("加载数据中，请稍候...", "取消", 0, 0, None)
    progress.setWindowTitle("工位SOP助手")
    progress.setWindowModality(Qt.WindowModal)
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.resize(400, 120)
    progress.setMinimumSize(350, 100)
    progress.show()
    app.processEvents()

    # ====== 7. 数据加载 + 主窗口 ======
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

            # ====== 每小时静默检查更新 ======
            from app.core.cloud_sync import sync_cloud, sync_license_file

            def hourly_sync():
                ok, new_cloud_root = sync_cloud(SOFTWARE_VERSION, silent=True)
                if ok and new_cloud_root:
                    sync_license_file(new_cloud_root)

            timer = QTimer()
            timer.timeout.connect(hourly_sync)
            timer.start(60 * 60 * 1000)  # 1小时
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