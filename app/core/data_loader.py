import os
import sys
import json
import base64
import importlib.util
from pathlib import Path
from typing import Optional, Dict, List, Any

XOR_KEY = 0x5A

def xor_deobfuscate(data: bytes) -> bytes:
    return bytes([b ^ XOR_KEY for b in data])

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent

class DataLoader:
    _instance = None
    _assets = None
    _decrypted_knowledge_graph = None
    _current_version = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        base_dir = get_base_path()
        assets_dir = base_dir / "assets"
        version_path = assets_dir / "version.json"

        if version_path.exists():
            try:
                with open(version_path, "r", encoding="utf-8") as f:
                    version = json.load(f).get("embedded_assets")
                if version:
                    module_name = f"embedded_assets_{version}"
                    module_path = assets_dir / f"{module_name}.py"
                    if module_path.exists():
                        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self._assets = module.ASSETS
                        self._current_version = version
                        # 数据已在编译时过滤，无需额外处理
                        print(f"✅ 数据加载成功，版本: {version}")
                        return
            except Exception as e:
                print(f"⚠️ 加载资产失败: {e}，回退到开发模式")

        # 开发模式（直接读取 data/ 目录，同时进行过滤）
        print("ℹ️ 数据加载器：未找到有效资产，尝试读取 data/ 目录（开发模式）")
        data_dir = base_dir / "data"
        self._assets = {}

        kg_path = data_dir / "knowledge_graph" / "doc_nodes.json"
        if kg_path.exists():
            try:
                with open(kg_path, "r", encoding="utf-8") as f:
                    self._assets["knowledge_graph"] = json.load(f)
            except:
                self._assets["knowledge_graph"] = {"documents": []}
        else:
            self._assets["knowledge_graph"] = {"documents": []}

        config_path = data_dir / "configs" / "station_mapping.json"
        station_mapping = {}
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    station_mapping = json.load(f)
            except:
                station_mapping = {}

        # 过滤 PDF 存在性
        station_to_pdfs_filtered = {}
        file_categories = {}
        pdf_dir = data_dir / "pdf_library"
        for pdf_name, info in station_mapping.items():
            pdf_file = pdf_dir / f"{pdf_name}.pdf"
            if pdf_file.exists():
                stations = info.get("stations", [])
                for station in stations:
                    if station not in station_to_pdfs_filtered:
                        station_to_pdfs_filtered[station] = []
                    station_to_pdfs_filtered[station].append(pdf_name)
                file_categories[pdf_name] = info.get("category", "")
        self._assets["station_mapping"] = station_mapping
        self._assets["station_to_pdfs_filtered"] = station_to_pdfs_filtered
        self._assets["file_categories"] = file_categories

        # 开发模式下题库直接从 data/quiz_bank 读取，但这里留空，由 get_quiz_bank 按需加载
        self._assets["quiz_bank"] = {}
        self._assets["available_quiz_names"] = []

        self._pdf_dir = pdf_dir
        self._current_version = None
        print("✅ 数据加载器：从 data/ 目录加载完成（开发模式）")

    # ---------- 公开接口 ----------
    def get_knowledge_graph(self) -> dict:
        if self._decrypted_knowledge_graph is not None:
            return self._decrypted_knowledge_graph
        kg_data = self._assets.get("knowledge_graph")
        if isinstance(kg_data, str):
            try:
                obfuscated = base64.b64decode(kg_data)
                decrypted_bytes = xor_deobfuscate(obfuscated)
                kg_str = decrypted_bytes.decode('utf-8')
                self._decrypted_knowledge_graph = json.loads(kg_str)
                print("✅ 知识图谱解密成功")
                return self._decrypted_knowledge_graph
            except Exception as e:
                print(f"⚠️ 知识图谱解密失败: {e}")
                self._decrypted_knowledge_graph = {"documents": []}
                return self._decrypted_knowledge_graph
        elif isinstance(kg_data, dict):
            self._decrypted_knowledge_graph = kg_data
            return kg_data
        else:
            self._decrypted_knowledge_graph = {"documents": []}
            return self._decrypted_knowledge_graph

    def get_station_mapping(self) -> dict:
        return self._assets.get("station_mapping", {})

    def get_file_categories(self) -> dict:
        return self._assets.get("file_categories", {})

    def get_station_to_pdfs(self) -> dict:
        return self._assets.get("station_to_pdfs_filtered", {})

    def get_all_stations(self) -> list:
        return list(self.get_station_to_pdfs().keys())

    def get_available_quiz_names(self) -> list:
        return self._assets.get("available_quiz_names", [])

    def get_pdf_bytes(self, pdf_name: str) -> Optional[bytes]:
        full_name = pdf_name + ".pdf"
        if "pdfs" in self._assets and full_name in self._assets["pdfs"]:
            encoded = self._assets["pdfs"][full_name]
            if isinstance(encoded, str):
                try:
                    obfuscated = base64.b64decode(encoded)
                    return xor_deobfuscate(obfuscated)
                except Exception as e:
                    print(f"⚠️ PDF 解密失败: {full_name}, {e}")
                    return None
            return encoded
        if hasattr(self, '_pdf_dir') and self._pdf_dir and self._pdf_dir.exists():
            pdf_path = self._pdf_dir / full_name
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    return f.read()
        return None

    def get_all_pdf_names(self) -> list:
        if "pdfs" in self._assets:
            return [name[:-4] for name in self._assets["pdfs"].keys() if name.endswith(".pdf")]
        if hasattr(self, '_pdf_dir') and self._pdf_dir and self._pdf_dir.exists():
            return [f.name[:-4] for f in self._pdf_dir.glob("*.pdf")]
        return []

    def get_quiz_bank(self) -> dict:
        return self._assets.get("quiz_bank", {})

    def get_current_version(self) -> Optional[str]:
        return self._current_version

    def check_update(self) -> bool:
        base_dir = get_base_path()
        assets_dir = base_dir / "assets"
        version_path = assets_dir / "version.json"
        if not version_path.exists():
            return False
        try:
            with open(version_path, "r", encoding="utf-8") as f:
                new_version = json.load(f).get("embedded_assets")
            if not new_version or new_version == self._current_version:
                return False
            print(f"🔄 检测到新版本数据: {new_version} (当前: {self._current_version})")
            self._decrypted_knowledge_graph = None
            self._current_version = None
            self._assets = None
            self._load()
            return True
        except Exception as e:
            print(f"⚠️ 检查更新失败: {e}")
            return False

DATA_LOADER = DataLoader()