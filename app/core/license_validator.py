import os
import sys
import base64
from pathlib import Path
from datetime import datetime, timedelta
from PyQt5.QtWidgets import QApplication, QMessageBox, QInputDialog, QLineEdit

XOR_KEY_DATE = 0x3C

def xor_date_obfuscate(data: bytes) -> bytes:
    return bytes([b ^ XOR_KEY_DATE for b in data])

def xor_date_deobfuscate(data: bytes) -> bytes:
    return bytes([b ^ XOR_KEY_DATE for b in data])

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent


class LicenseValidator:
    """软件有效期验证类，独立于数据加载"""

    @staticmethod
    def get_expiry_date() -> datetime | None:
        """从 assets/sequence.dat 读取并解密到期日期，若文件不存在则返回 None"""
        base_dir = get_base_path()
        seq_file = base_dir / "assets" / "sequence.dat"
        if not seq_file.exists():
            return None
        try:
            with open(seq_file, "rb") as f:
                enc_data = f.read()
            decrypted = xor_date_deobfuscate(enc_data)
            date_str = decrypted.decode('utf-8')
            return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception as e:
            print(f"[LicenseValidator] 读取有效期失败: {e}")
            return None

    @staticmethod
    def set_expiry_date(expiry_date: datetime):
        """加密并存储到期日期到 assets/sequence.dat"""
        base_dir = get_base_path()
        assets_dir = base_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        seq_file = assets_dir / "sequence.dat"
        date_str = expiry_date.strftime("%Y-%m-%d")
        enc_data = xor_date_obfuscate(date_str.encode('utf-8'))
        with open(seq_file, "wb") as f:
            f.write(enc_data)

    @staticmethod
    def is_expired() -> bool:
        expiry = LicenseValidator.get_expiry_date()
        if expiry is None:
            return True
        return datetime.now() > expiry

    @staticmethod
    def update_expiry_with_sequence(input_seq: str) -> bool:
        """验证授权码（Base64 加密的日期），若有效则更新到期日期并返回 True"""
        try:
            raw_bytes = base64.b64decode(input_seq.strip())
            decrypted = xor_date_deobfuscate(raw_bytes)
            date_str = decrypted.decode('utf-8')
            for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
                try:
                    new_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return False
            if new_date <= datetime.now():
                return False
            LicenseValidator.set_expiry_date(new_date)
            return True
        except Exception:
            return False

    @staticmethod
    def prompt_for_license(parent=None):
        """
        弹窗要求输入授权码（明文显示），若验证通过返回 True，否则继续等待输入或退出。
        此方法会阻塞直到输入有效授权码或用户取消。
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        while True:
            dialog = QInputDialog()
            dialog.setInputMode(QInputDialog.TextInput)
            dialog.setLabelText("请输入授权码：")
            dialog.setTextEchoMode(QLineEdit.Normal)   # 明文显示
            dialog.setWindowTitle("授权验证")
            dialog.resize(400, 120)                    # 加大弹窗
            ok = dialog.exec_()
            seq = dialog.textValue() if ok else ""
            if not ok:
                sys.exit(0)                            # 用户取消，退出程序
            if LicenseValidator.update_expiry_with_sequence(seq):
                return True
            else:
                QMessageBox.warning(
                    parent if parent else None,
                    "授权失败",
                    "授权码无效，请重新输入。"
                )