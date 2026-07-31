import sys
import traceback
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt, QTimer, QSharedMemory
from PyQt5.QtGui import QFont

from app.core.license_validator import LicenseValidator   # 新增导入



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
# 单实例检测（使用 QSharedMemory 固定密钥）
# ============================================================
def check_single_instance():
    """
    使用共享内存检测是否已有实例在运行。
    密钥固定为 '796796796'。
    """
    shared_memory = QSharedMemory("796796796")
    if shared_memory.attach():
        # 已存在共享内存 -> 已有实例
        return False
    else:
        # 创建共享内存，大小为1字节
        if shared_memory.create(1):
            # 创建成功，保存引用到 app 防止被回收
            app = QApplication.instance()
            app._single_shared_memory = shared_memory
            return True
        else:
            # 创建失败（可能被其他进程占用），视为已有实例
            return False





# ============================================================
# 主程序入口
# ============================================================
def main():
    
    # # 授权检查
    # if not check_license():
    #     show_license_error()
    #     return
    
    # 有效期检查（软件到期时间）
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # 检查有效期，若需要则弹窗输入授权码
    if LicenseValidator.is_expired():
        LicenseValidator.prompt_for_license()
        
    # ---------- 单实例检测 ----------
    if not check_single_instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("提示")
        msg.setText("程序已在运行中，请勿重复打开。")
        msg.exec_()
        sys.exit(0)

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

    # ---------- 定义数据加载函数 ----------
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

        # ---------- 创建主窗口 ----------
        try:
            from app.main_window import MainWindow
            window = MainWindow()
            window.show()
            window.raise_()
            window.activateWindow()
            app.main_window = window
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(None, "启动失败", f"创建主窗口失败：\n{str(e)}")
            sys.exit(1)

    # ---------- 启动定时器，延迟执行加载 ----------
    QTimer.singleShot(10, load_data)

    # ---------- 进入事件循环 ----------
    try:
        exit_code = app.exec_()
        # 释放共享内存（可选）
        if hasattr(app, '_single_shared_memory'):
            app._single_shared_memory.detach()
        sys.exit(exit_code)
    except Exception as e:
        print(f"[ERROR] 事件循环异常: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()