"""本地嵌入模型 + Chroma 持久化向量库。"""

from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass
import re
from difflib import SequenceMatcher
import chromadb
from sentence_transformers import SentenceTransformer

from src.config import Settings, settings
from src.rag.splitter import TextChunk


@dataclass(frozen=True)
class SearchResult:
    text: str
    source: str
    location: str
    chunk_index: int
    distance: float | None

    @property
    def citation(self) -> str:
        return f"{self.source}｜{self.location}｜片段{self.chunk_index}"


class VectorStore:
    def __init__(self, config: Settings = settings):
        self.config = config
        self.client = chromadb.PersistentClient(path=config.chroma_path)
        self.collection = self.client.get_or_create_collection(
            name=config.collection_name,
            embedding_function=None,
        )
        self.encoder = SentenceTransformer(config.embedding_model)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.encoder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    @staticmethod
    def _chunk_id(chunk: TextChunk) -> str:
        raw = (
            f"{chunk.source}|{chunk.location}|{chunk.chunk_index}|{chunk.text}"
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def add_chunks(self, chunks: list[TextChunk], batch_size: int = 64) -> int:
        if not chunks:
            return 0
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            documents = [chunk.text for chunk in batch]
            self.collection.upsert(
                ids=[self._chunk_id(chunk) for chunk in batch],
                documents=documents,
                metadatas=[
                    {
                        "source": chunk.source,
                        "location": chunk.location,
                        "chunk_index": chunk.chunk_index,
                    }
                    for chunk in batch
                ],
                embeddings=self._encode(documents),
            )
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        检索顺序：

        1. 从知识库记录中提取“功能主题”
        2. 对用户问题和功能主题进行文本标准化
        3. 优先进行精确匹配和近似匹配
        4. 功能主题匹配不到时，再使用向量检索

        注意：
        知识库文本中需要包含如下格式：
            功能主题: 查询号码的余额/充值金额
            SQL正文开始
            ...
            SQL正文结束
        """

        query = query.strip()

        if not query:
            return []

        collection_count = self.count()

        if collection_count == 0:
            return []

        result_limit = min(
            top_k or self.config.top_k,
            collection_count,
        )

        def normalize_function_text(text: str) -> str:
            """
            将用户问题和功能主题转换成便于比较的形式。

            例如：
            “查询号码的余额/充值金额”
            “查号码的余额/充值金额”
            最终都会接近：
            “号码余额充值金额”
            """

            text = str(text).strip().lower()

            # 去掉常见的提问语气
            prefix_patterns = [
                r"^(?:你好|您好)",
                r"^(?:请问|麻烦问一下|麻烦帮我|帮我|请帮我)",
                r"^(?:我想知道|我想了解|我想查询|我想查|想知道|想了解)",
                r"^(?:能不能|能否|是否可以|可以)",
            ]

            changed = True

            while changed:
                original_text = text

                for pattern in prefix_patterns:
                    text = re.sub(pattern, "", text).strip()

                changed = text != original_text

            # “怎么对一次性费用表加工”
            # 转换成“一次性费用表加工”
            text = re.sub(
                r"^(?:怎么|如何|怎样)(?:对|把)?",
                "",
                text,
            )

            # 去掉查询类前缀
            text = re.sub(
                r"^(?:查询一下|查一下|查询|查找|搜索|检索|查)",
                "",
                text,
            )

            # 去掉句子中对功能匹配没有帮助的词
            text = re.sub(
                r"(?:怎么|如何|怎样)",
                "",
                text,
            )

            # 去掉残留在开头的“对、把”
            text = re.sub(r"^(?:对|把)", "", text)

            # 去掉空格、标点和“的”
            text = re.sub(
                r"[\s，。！？、；：:,.!?;／/\\（）()【】\[\]《》<>_\-—]+",
                "",
                text,
            )

            text = text.replace("的", "")

            return text

        def extract_function_theme(document: str) -> str | None:
            """从知识库文本中提取功能主题。"""

            match = re.search(
                r"(?im)^\s*功能主题\s*[:：]\s*(.*?)\s*$",
                document,
            )

            if not match:
                return None

            function_theme = match.group(1).strip()

            return function_theme or None

        def build_search_result(
            document: str,
            metadata: dict | None,
            distance: float | None,
            default_index: int,
        ) -> SearchResult:
            """统一创建 SearchResult。"""

            metadata = metadata or {}

            chunk_index_value = metadata.get(
                "chunk_index",
                default_index,
            )

            try:
                chunk_index = int(chunk_index_value)
            except (TypeError, ValueError):
                chunk_index = default_index

            return SearchResult(
                text=document,
                source=str(
                    metadata.get("source", "未知来源")
                ),
                location=str(
                    metadata.get("location", "未知位置")
                ),
                chunk_index=chunk_index,
                distance=(
                    float(distance)
                    if distance is not None
                    else None
                ),
            )

        normalized_query = normalize_function_text(query)

        # -------------------------------------------------
        # 第一阶段：按“功能主题”匹配
        # -------------------------------------------------

        try:
            # 只读取包含“功能主题:”的结构化SQL记录
            stored_data = self.collection.get(
                where_document={
                    "$contains": "功能主题:"
                },
                include=[
                    "documents",
                    "metadatas",
                ],
            )

        except Exception:
            # 如果当前 Chroma 版本不支持 where_document，
            # 就读取全部文档，再由下面的代码过滤。
            stored_data = self.collection.get(
                include=[
                    "documents",
                    "metadatas",
                ],
            )

        stored_documents = stored_data.get("documents") or []
        stored_metadatas = stored_data.get("metadatas") or []

        function_candidates: list[
            tuple[float, SearchResult]
        ] = []

        for index, document in enumerate(stored_documents):
            if not document:
                continue

            function_theme = extract_function_theme(document)

            if not function_theme:
                continue

            normalized_theme = normalize_function_text(
                function_theme
            )

            if not normalized_query or not normalized_theme:
                continue

            # 完全一致
            if normalized_query == normalized_theme:
                similarity = 1.0

            # 一方完整包含另一方
            elif (
                len(normalized_query) >= 4
                and len(normalized_theme) >= 4
                and (
                    normalized_query in normalized_theme
                    or normalized_theme in normalized_query
                )
            ):
                shorter_length = min(
                    len(normalized_query),
                    len(normalized_theme),
                )

                longer_length = max(
                    len(normalized_query),
                    len(normalized_theme),
                )

                coverage = shorter_length / longer_length

                similarity = 0.93 + 0.06 * coverage

            else:
                # 处理少量表达差异
                similarity = SequenceMatcher(
                    None,
                    normalized_query,
                    normalized_theme,
                ).ratio()

            metadata = (
                stored_metadatas[index]
                if index < len(stored_metadatas)
                else {}
            )

            search_result = build_search_result(
                document=document,
                metadata=metadata,
                distance=1.0 - similarity,
                default_index=index,
            )

            function_candidates.append(
                (
                    similarity,
                    search_result,
                )
            )

        if function_candidates:
            function_candidates.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            best_similarity = function_candidates[0][0]

            # 如果存在完全匹配，只返回完全匹配的记录。
            # 同一个功能可能有多条SQL步骤，因此不会只取第一条。
            exact_matches = [
                search_result
                for similarity, search_result
                in function_candidates
                if similarity >= 0.999
            ]

            if exact_matches:
                return exact_matches[:result_limit]

            # 没有完全匹配时，接受相似度较高的功能主题
            function_match_threshold = 0.78

            if best_similarity >= function_match_threshold:
                similarity_cutoff = max(
                    function_match_threshold,
                    best_similarity - 0.02,
                )

                similar_matches = [
                    search_result
                    for similarity, search_result
                    in function_candidates
                    if similarity >= similarity_cutoff
                ]

                if similar_matches:
                    return similar_matches[:result_limit]

        # -------------------------------------------------
        # 第二阶段：功能主题没匹配到，再使用向量检索
        # -------------------------------------------------

        vector_result = self.collection.query(
            query_embeddings=self._encode([query]),
            n_results=result_limit,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        vector_documents = (
            vector_result.get("documents") or [[]]
        )[0]

        vector_metadatas = (
            vector_result.get("metadatas") or [[]]
        )[0]

        vector_distances = (
            vector_result.get("distances") or [[]]
        )[0]

        output: list[SearchResult] = []

        for index, document in enumerate(vector_documents):
            if not document:
                continue

            metadata = (
                vector_metadatas[index]
                if index < len(vector_metadatas)
                else {}
            )

            distance = (
                vector_distances[index]
                if index < len(vector_distances)
                else None
            )

            output.append(
                build_search_result(
                    document=document,
                    metadata=metadata,
                    distance=distance,
                    default_index=index,
                )
            )

        return output

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        self.client.delete_collection(self.config.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.config.collection_name,
            embedding_function=None,
        )

    @staticmethod
    def _normalize_function_query(query: str) -> str:
        text = query.strip()

        text = re.sub(
            r"[？?!！。]+$",
            "",
            text,
        )

        text = re.sub(
            r"^(请问|麻烦问一下|麻烦|帮我|我想知道|怎么|如何)",
            "",
            text,
        )

        # “直销客户类型怎么查询”转换为“查询直销客户类型”
        match = re.fullmatch(
            r"(.+?)(?:怎么|如何)查询",
            text,
        )

        if match:
            text = f"查询{match.group(1)}"

        return text.strip()

    def _search_by_function_theme(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        query_normalized = self._normalize_function_text(query)

        if not query_normalized:
            return []

        # 读取结构化SQL记录
        result = self.collection.get(
            include=[
                "documents",
                "metadatas",
            ]
        )

        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        matches = []

        for index, document in enumerate(documents):
            function_theme = self._extract_function_theme(document)

            if not function_theme:
                continue

            function_normalized = self._normalize_function_text(
                function_theme
            )

            if not function_normalized:
                continue

            # 第一优先级：归一化后完全相同
            if query_normalized == function_normalized:
                score = 1.0

            # 第二优先级：一个名称包含另一个名称
            elif (
                len(query_normalized) >= 4
                and (
                    query_normalized in function_normalized
                    or function_normalized in query_normalized
                )
            ):
                score = 0.92

            # 第三优先级：文字相似度
            elif len(query_normalized) >= 4:
                score = SequenceMatcher(
                    None,
                    query_normalized,
                    function_normalized,
                ).ratio()

                if score < 0.78:
                    continue
            else:
                continue

            metadata = metadatas[index] or {}

            matches.append(
                (
                    score,
                    SearchResult(
                        text=document,
                        source=str(
                            metadata.get("source", "未知来源")
                        ),
                        location=str(
                            metadata.get("location", "未知位置")
                        ),
                        chunk_index=int(
                            metadata.get("chunk_index", 0)
                        ),
                        # 分数越高，距离越低
                        distance=1.0 - score,
                    ),
                )
            )

        # 相似度从高到低排序
        matches.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        output = []
        seen = set()

        for _, item in matches:
            key = (
                item.source,
                item.location,
            )

            if key in seen:
                continue

            seen.add(key)
            output.append(item)

            if len(output) >= limit:
                break

        return output