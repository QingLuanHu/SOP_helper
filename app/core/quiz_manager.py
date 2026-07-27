import json
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox


class QuizManager:
    """考核记录管理（加载/保存、版本校验、颜色渐变）"""
    def __init__(self, parent):
        self.parent = parent
        self.quiz_records = {}
        self.records_file_path = None

    def load_records(self):
        if not self.parent.logged_in:
            return
        username = self.parent.current_user if self.parent.current_user else "admin"
        records_dir = Path("D:/SOP_helper")
        records_dir.mkdir(parents=True, exist_ok=True)
        self.records_file_path = records_dir / f"{username}.json"

        if not self.records_file_path.exists():
            self.quiz_records = {}
            self.save_records()
            return

        try:
            with open(self.records_file_path, "r", encoding="utf-8") as f:
                self.quiz_records = json.load(f)
        except Exception:
            self.quiz_records = {}
            self.save_records()
            return

        # 版本校验
        quiz_bank = self.parent.knowledge_data.get("quiz_bank", {})
        updated = False
        for pdf_name in list(self.quiz_records.keys()):
            record = self.quiz_records[pdf_name]
            latest_version = quiz_bank.get(pdf_name, {}).get("version", "")
            if not latest_version or record.get("version") != latest_version:
                self.quiz_records[pdf_name] = {
                    "version": latest_version,
                    "answers": [],
                    "score": 0,
                    "submitted": False
                }
                updated = True

        if updated:
            self.save_records()

    def save_records(self):
        if not self.records_file_path:
            return
        try:
            with open(self.records_file_path, "w", encoding="utf-8") as f:
                json.dump(self.quiz_records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存答题记录失败: {e}")

    def get_record(self, pdf_name):
        return self.quiz_records.get(pdf_name, {})

    def update_record(self, pdf_name, version, answers, score, submitted=False):
        record = self.quiz_records.get(pdf_name, {})
        record["version"] = version
        record["answers"] = answers
        record["score"] = score
        record["submitted"] = submitted
        record["timestamp"] = datetime.now().isoformat()
        self.quiz_records[pdf_name] = record
        self.save_records()

    @staticmethod
    def score_to_color(score):
        score = max(0, min(100, score))
        if score <= 50:
            ratio = score / 50.0
            r = 255
            g = int(255 * ratio)
            b = 0
        else:
            ratio = (score - 50) / 50.0
            r = int(255 * (1 - ratio))
            g = 255
            b = 0
        return r, g, b