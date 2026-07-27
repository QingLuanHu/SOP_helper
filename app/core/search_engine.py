import re


class SearchEngine:
    """搜索索引构建与关键词检索"""
    def __init__(self, parent):
        self.parent = parent

    def build_dynamic_index(self):
        """根据当前工站和分类筛选，构建动态索引"""
        pdf_list = self.parent.station_to_pdfs.get(self.parent.current_station, [])
        show_general = self.parent.top_bar.checkbox_general.isChecked()
        show_product = self.parent.top_bar.checkbox_product.isChecked()
        if show_general or show_product:
            filtered = []
            for pdf_name in pdf_list:
                category = self.parent.file_categories.get(pdf_name, "")
                if show_general and category == "通用操作":
                    filtered.append(pdf_name)
                elif show_product and category == "产品相关":
                    filtered.append(pdf_name)
            pdf_list = filtered

        docs = self.parent.knowledge_data.get("documents", [])
        pdf_name_set = set(pdf_list)
        matched_docs = [doc for doc in docs if doc.get("pdf_name", "") in pdf_name_set]
        self.parent.search_index = self._build_flat_index(matched_docs)
        return self.parent.search_index

    def _build_flat_index(self, documents):
        """将文档节点列表转换为扁平索引（去重）"""
        index = []
        seen = set()
        for doc in documents:
            doc_code = doc.get("doc_code", "")
            doc_name = doc.get("doc_name", "")
            pdf_name = doc.get("pdf_name", "")
            for proc in doc.get("processes", []):
                process_name = proc.get("name", "")
                pdf_page = proc.get("page", "N/A")
                content_items = proc.get("content", [])
                if not content_items:
                    continue
                if isinstance(content_items, list):
                    for item in content_items:
                        if isinstance(item, dict):
                            step_item = item.get("item_name", "")
                            content = item.get("content", "")
                            precautions = item.get("precautions", "")
                            key = (doc_code, process_name, step_item, content, precautions)
                            if key in seen:
                                continue
                            seen.add(key)
                            index.append({
                                "doc_code": doc_code,
                                "doc_name": doc_name,
                                "pdf_name": pdf_name,
                                "process_name": process_name,
                                "step_item": step_item,
                                "content": content,
                                "precautions": precautions,
                                "pdf_page": pdf_page,
                            })
                        elif isinstance(item, str):
                            key = (doc_code, process_name, "", item, "")
                            if key in seen:
                                continue
                            seen.add(key)
                            index.append({
                                "doc_code": doc_code,
                                "doc_name": doc_name,
                                "pdf_name": pdf_name,
                                "process_name": process_name,
                                "step_item": "",
                                "content": item,
                                "precautions": "",
                                "pdf_page": pdf_page,
                            })
                elif isinstance(content_items, dict):
                    pass
        return index

    def keyword_search(self, query, index):
        """在动态索引中执行关键词检索（优化版）"""
        if not query.strip() or not index:
            return []

        words = [w.strip() for w in re.split(r'[，,、。.；;：:！!？? \t\n\r]+', query) if w.strip()]
        if not words:
            return []

        results = []
        for record in index:
            score = 0
            matched_words = []
            doc_code_lower = record["doc_code"].lower()
            doc_name_lower = record["doc_name"].lower()
            process_name_lower = record["process_name"].lower()
            step_item_lower = record["step_item"].lower()
            content_lower = record["content"].lower()
            precautions_lower = record["precautions"].lower()

            for word in words:
                word_lower = word.lower()
                weight_boost = 1.5 if word.isdigit() else 1.0
                found = False

                if word_lower in doc_code_lower:
                    score += int(20 * weight_boost)
                    matched_words.append(word)
                    found = True
                if word_lower in doc_name_lower:
                    score += int(15 * weight_boost)
                    if not found:
                        matched_words.append(word)
                        found = True
                if word_lower in process_name_lower:
                    score += int(12 * weight_boost)
                    if not found:
                        matched_words.append(word)
                        found = True
                if word_lower in step_item_lower:
                    score += int(10 * weight_boost)
                    if not found:
                        matched_words.append(word)
                        found = True
                if word_lower in content_lower:
                    # 改为固定分，不再乘以出现次数
                    score += int(3 * weight_boost)
                    if not found:
                        matched_words.append(word)
                        found = True
                if word_lower in precautions_lower:
                    # 改为固定分
                    score += int(2 * weight_boost)
                    if not found:
                        matched_words.append(word)
                        found = True

            if score > 0:
                match_ratio = len(set(matched_words)) / len(words) if words else 0
                results.append({
                    "record": record,
                    "score": score,
                    "match_ratio": match_ratio,
                    "matched_words": list(set(matched_words)),
                })

        # 排序：先按匹配率（所有关键词都命中的优先），再按总分
        results.sort(key=lambda x: (x["match_ratio"], x["score"]), reverse=True)
        return [r["record"] for r in results[:30]]