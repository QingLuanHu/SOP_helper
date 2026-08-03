# app/core/cloud_sync.py
import json
import sys
import shutil
import tempfile
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

    # 同步 CloudBasePath
    local_path = normalize_path(local_manifest.get("CloudBasePath", ""))
    remote_path = normalize_path(cloud_manifest.get("CloudBasePath", ""))
    if local_path != remote_path and remote_path:
        updated_manifest["CloudBasePath"] = cloud_manifest["CloudBasePath"]
        cloud_root = remote_path
        cloud_root_path = Path(cloud_root)
        need_update = True

    # 同步 SoftwareVersion
    local_sw = local_manifest.get("SoftwareVersion", "")
    remote_sw = cloud_manifest.get("SoftwareVersion", "")
    if local_sw != remote_sw and remote_sw:
        updated_manifest["SoftwareVersion"] = remote_sw
        need_update = True

    # 同步 embedded_assets（增加物理文件检查，不删除旧文件）
    local_ver = local_manifest.get("embedded_assets", "")
    remote_ver = cloud_manifest.get("embedded_assets", "")

    # ★ 检查本地数据文件是否存在
    local_file_exists = False
    if local_ver:
        local_file = local_data_dir / f"embedded_assets_{local_ver}.py"
        local_file_exists = local_file.exists()

    # 条件：云端有版本（remote_ver非空）且（本地版本不同 或 本地文件缺失）
    if remote_ver and (local_ver != remote_ver or not local_file_exists):
        remote_file = cloud_root_path / f"embedded_assets_{remote_ver}.py"
        if not remote_file.exists():
            if not silent:
                QMessageBox.critical(None, "下载失败", f"云端文件不存在：{remote_file}")
            return False, "云端数据文件缺失"
        try:
            # 直接复制（覆盖目标文件，若已存在则覆盖修复）
            shutil.copy2(str(remote_file), str(local_data_dir / f"embedded_assets_{remote_ver}.py"))
            # ★ 不删除旧版本文件
            updated_manifest["embedded_assets"] = remote_ver
            need_update = True
        except Exception as e:
            if not silent:
                QMessageBox.critical(None, "复制失败", f"无法复制新数据文件：{e}")
            return False, "数据文件复制失败"

    if need_update:
        write_local_manifest(updated_manifest)

    # 软件版本校验
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