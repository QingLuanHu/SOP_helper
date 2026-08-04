# app/core/cloud_sync.py
import json
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple
from PyQt5.QtWidgets import QMessageBox


def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent


ASSETS_DIR = get_base_path() / "assets"
VERSION_FILE = ASSETS_DIR / "version.json"


def normalize_path(path: str) -> str:
    if not path:
        return path
    path = path.strip().replace('/', '\\')
    if path.startswith('\\\\') or (len(path) >= 3 and path[1] == ':' and path[2] == '\\'):
        return path
    return '\\\\' + path


def read_local_manifest() -> Optional[dict]:
    if not VERSION_FILE.exists():
        return None
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def write_local_manifest(manifest: dict):
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def sync_license_file(cloud_root: str) -> bool:
    """
    从云端复制 sequence.dat 到本地 assets/（静默，不弹窗）
    云端路径：{cloud_root}/sequence.dat
    本地路径：assets/sequence.dat
    返回 True 表示复制成功或无需复制，False 表示复制失败（已静默处理）
    """
    cloud_root_path = Path(cloud_root)
    cloud_seq = cloud_root_path / "sequence.dat"
    local_seq = ASSETS_DIR / "sequence.dat"

    # 云端文件不存在 → 跳过
    if not cloud_seq.exists():
        return False

    # 云端文件大小为 0 → 跳过
    if cloud_seq.stat().st_size == 0:
        return False

    # 本地已有且大小与云端一致 → 跳过（避免无效写入）
    if local_seq.exists() and local_seq.stat().st_size > 0:
        if local_seq.stat().st_size == cloud_seq.stat().st_size:
            return True

    try:
        local_seq.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(cloud_seq), str(local_seq))
        # 验证复制结果
        if not local_seq.exists() or local_seq.stat().st_size == 0:
            print(f"[云同步] 复制 sequence.dat 后文件为空，保留原有授权")
            return False
        return True
    except Exception as e:
        print(f"[云同步] 复制 sequence.dat 失败: {e}")
        return False


def sync_cloud(local_software_version: str, silent: bool = False) -> Tuple[bool, str]:
    local_manifest = read_local_manifest()
    if local_manifest is None:
        if not silent:
            QMessageBox.critical(None, "配置缺失", "未找到 assets/version.json，无法获取云配置。")
        return False, "本地配置缺失"

    cloud_base = local_manifest.get("CloudBasePath", "")
    if not cloud_base:
        return True, "无云配置"

    cloud_root = normalize_path(cloud_base)
    local_data_dir = ASSETS_DIR

    try:
        if Path(cloud_root).resolve() == local_data_dir.resolve():
            return True, "云路径指向本地，跳过同步"
    except:
        pass

    cloud_root_path = Path(cloud_root)
    if not cloud_root_path.exists():
        if not silent:
            QMessageBox.warning(None, "连接警告", f"云盘连接异常：{cloud_root}\n将使用本地数据继续运行。")
        return True, "云盘不可达"

    cloud_manifest_path = cloud_root_path / "version.json"
    if not cloud_manifest_path.exists():
        return True, "云端无 version.json"

    try:
        with open(cloud_manifest_path, 'r', encoding='utf-8') as f:
            cloud_manifest = json.load(f)
    except:
        return True, "云端 version.json 解析失败"

    need_update = False
    updated_manifest = local_manifest.copy()

    # ---- 1. 同步 CloudBasePath ----
    local_path = normalize_path(local_manifest.get("CloudBasePath", ""))
    remote_path = normalize_path(cloud_manifest.get("CloudBasePath", ""))
    if local_path != remote_path and remote_path:
        updated_manifest["CloudBasePath"] = cloud_manifest["CloudBasePath"]
        cloud_root = remote_path          # 更新 cloud_root 为新路径
        cloud_root_path = Path(cloud_root)
        need_update = True

    # ---- 2. 同步 SoftwareVersion ----
    local_sw = local_manifest.get("SoftwareVersion", "")
    remote_sw = cloud_manifest.get("SoftwareVersion", "")
    if local_sw != remote_sw and remote_sw:
        updated_manifest["SoftwareVersion"] = remote_sw
        need_update = True

    # ---- 3. 同步 embedded_assets（数据文件，不删除旧文件） ----
    local_ver = local_manifest.get("embedded_assets", "")
    remote_ver = cloud_manifest.get("embedded_assets", "")

    # 检查本地数据文件是否存在（防止文件被意外删除）
    local_file_exists = False
    if local_ver:
        local_file = local_data_dir / f"embedded_assets_{local_ver}.py"
        local_file_exists = local_file.exists()

    # 若云端有版本，且（本地版本不同 或 本地文件缺失），则从云端复制
    if remote_ver and (local_ver != remote_ver or not local_file_exists):
        remote_file = cloud_root_path / f"embedded_assets_{remote_ver}.py"
        if not remote_file.exists():
            if not silent:
                QMessageBox.critical(None, "下载失败", f"云端文件不存在：{remote_file}")
            return False, "云端数据文件缺失"

        # 检查云端文件大小
        if remote_file.stat().st_size == 0:
            if not silent:
                QMessageBox.critical(None, "下载失败", f"云端文件大小为 0，可能已损坏：{remote_file}")
            return False, "云端数据文件损坏"

        try:
            local_target = local_data_dir / f"embedded_assets_{remote_ver}.py"
            shutil.copy2(str(remote_file), str(local_target))
            # 验证复制结果
            if not local_target.exists() or local_target.stat().st_size == 0:
                if not silent:
                    QMessageBox.critical(None, "复制失败", f"复制后文件损坏或为空：{local_target}")
                if local_target.exists():
                    local_target.unlink()
                return False, "数据文件复制失败"

            updated_manifest["embedded_assets"] = remote_ver
            need_update = True
        except Exception as e:
            if not silent:
                QMessageBox.critical(None, "复制失败", f"无法复制新数据文件：{e}")
            return False, "数据文件复制失败"

    # ---- 4. 保存更新后的本地 version.json（包含 CloudBasePath/SoftwareVersion/embedded_assets） ----
    if need_update:
        write_local_manifest(updated_manifest)

    # ---- 5. ★ 从云端复制 sequence.dat 覆盖本地（无痕续期） ★ ----
    # 使用更新后的 cloud_root（可能已随 CloudBasePath 变化）
    sync_license_file(cloud_root)

    # ---- 6. 软件版本校验（阻断式） ----
    local_sw_after = updated_manifest.get("SoftwareVersion", "")
    if local_sw_after != local_software_version:
        if not silent:
            QMessageBox.critical(
                None,
                "版本错误",
                f"软件版本不匹配！\n当前程序版本：{local_software_version}\n所需数据版本：{local_sw_after}\n请更新软件。"
            )
        return False, "软件版本不匹配"

    return True, "同步完成"


def check_and_sync(local_software_version: str, silent: bool = False) -> bool:
    ok, _ = sync_cloud(local_software_version, silent)
    return ok