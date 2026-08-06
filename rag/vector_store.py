"""本地嵌入模型与Chroma向量数据库。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import chromadb
from sentence_transformers import (
    SentenceTransformer,
)

from src.config import (
    Settings,
    settings,
)
from src.rag.splitter import TextChunk


@dataclass(frozen=True)
class SearchResult:
    """知识库检索结果。"""

    text: str
    source: str
    location: str
    chunk_index: int
    distance: float | None

    # 数据库SQL记录新增字段
    record_id: int | None = None
    sql_id: str | None = None
    function_theme: str | None = None
    record_version: int | None = None

    @property
    def citation(self) -> str:
        return (
            f"{self.source}｜"
            f"{self.location}"
        )


class VectorStore:
    """Chroma向量数据库。"""

    def __init__(
        self,
        config: Settings = settings,
    ):
        self.config = config

        self.client = (
            chromadb.PersistentClient(
                path=config.chroma_path
            )
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=config.collection_name,
                embedding_function=None,
            )
        )

        self.encoder = SentenceTransformer(
            config.embedding_model
        )

    def _encode(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """把文本转换成向量。"""

        vectors = self.encoder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return vectors.tolist()

    # =====================================================
    # 普通上传文档
    # =====================================================

    @staticmethod
    def _chunk_id(
        chunk: TextChunk,
    ) -> str:
        """
        普通PDF、Word、TXT等文档继续使用
        内容哈希作为向量ID。
        """

        raw = (
            f"{chunk.source}|"
            f"{chunk.location}|"
            f"{chunk.chunk_index}|"
            f"{chunk.text}"
        ).encode("utf-8")

        return hashlib.sha256(
            raw
        ).hexdigest()

    def add_chunks(
        self,
        chunks: list[TextChunk],
        batch_size: int = 64,
    ) -> int:
        """
        添加普通文档文本块。

        该方法保留，用于非数据库管理的普通资料。
        """

        if not chunks:
            return 0

        for start in range(
            0,
            len(chunks),
            batch_size,
        ):
            batch = chunks[
                start:start + batch_size
            ]

            documents = [
                chunk.text
                for chunk in batch
            ]

            self.collection.upsert(
                ids=[
                    self._chunk_id(chunk)
                    for chunk in batch
                ],
                documents=documents,
                metadatas=[
                    {
                        "record_kind": "document",
                        "source": chunk.source,
                        "location": chunk.location,
                        "chunk_index": (
                            chunk.chunk_index
                        ),
                    }
                    for chunk in batch
                ],
                embeddings=self._encode(
                    documents
                ),
            )

        return len(chunks)

    # =====================================================
    # 数据库SQL记录
    # =====================================================

    @staticmethod
    def _sql_record_id(
        record_id: int,
    ) -> str:
        """
        数据库SQL记录使用稳定ID。

        SQL内容改变后，Chroma中的ID不会改变。
        """

        return (
            f"sql-record-{record_id}"
        )

    @staticmethod
    def _record_value(
        record: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        return getattr(
            record,
            field_name,
            default,
        )

    @classmethod
    def build_sql_record_text(
        cls,
        record: Any,
    ) -> str:
        """
        把数据库SQL记录转换成统一的向量文本。
        不把缺失表、未登记字段等内部信息放进去，
        避免Agent在回答时向用户展示内部检查信息。
        """
        sql_id = str(
            cls._record_value(
                record,
                "sql_id",
                "",
            )
            or ""
        ).strip()

        function_theme = str(
            cls._record_value(
                record,
                "function_theme",
                "",
            )
            or ""
        ).strip()

        sql_text = str(
            cls._record_value(
                record,
                "sql_text",
                "",
            )
            or ""
        ).strip()

        parts = [
            f"SQL_ID: {sql_id}",
            f"功能主题: {function_theme}",
        ]

        optional_fields = [
            (
                "business_domain",
                "业务域",
            ),
            (
                "step",
                "步骤",
            ),
            (
                "function_type",
                "功能类型",
            ),
            (
                "statement_type",
                "语句类型",
            ),
            (
                "source_tables",
                "涉及来源表",
            ),
            (
                "table_completeness",
                "表资料完整性",
            ),
            (
                "field_completeness",
                "字段资料完整性",
            ),
            (
                "notes",
                "备注",
            ),
        ]

        for field_name, display_name in optional_fields:
            value = cls._record_value(
                record,
                field_name,
                None,
            )

            if value is None:
                continue

            cleaned = str(value).strip()

            if cleaned:
                parts.append(
                    f"{display_name}: {cleaned}"
                )

        if sql_text:
            parts.extend(
                [
                    "SQL正文开始",
                    sql_text,
                    "SQL正文结束",
                ]
            )

        return "\n".join(parts)

    @classmethod
    def build_sql_retrieval_text(
        cls,
        record: Any,
    ) -> str:
        """
        生成专门用于向量检索的文本。
        这里只允许使用功能主题，
        不使用SQL正文、字段名、表名和备注，
        避免查询被字段内容干扰。
        """
        function_theme = str(
            cls._record_value(
                record,
                "function_theme",
                "",
            )
            or ""
        ).strip()

        if not function_theme:
            raise ValueError(
                "SQL记录缺少功能主题，"
                "无法生成检索向量。"
            )

        return (
            f"功能主题：{function_theme}"
        )

    def delete_sql_record(
        self,
        record_id: int,
    ) -> None:
        """删除某条数据库记录对应的全部向量。"""

        self.collection.delete(
            where={
                "record_id": int(record_id)
            }
        )

    def upsert_sql_record(
        self,
        record: Any,
    ) -> None:
        """
        新增或更新一条数据库SQL记录。

        record需要至少包含：
        id
        sql_id
        function_theme
        sql_text
        version
        """

        record_id = self._record_value(
            record,
            "id",
            None,
        )

        if record_id is None:
            raise ValueError(
                "SQL记录缺少数据库record_id。"
            )

        deleted_at = self._record_value(
            record,
            "deleted_at",
            None,
        )

        # 已经软删除的记录不应继续出现在向量库
        if deleted_at is not None:
            self.delete_sql_record(
                int(record_id)
            )
            return

        sql_id = str(
            self._record_value(
                record,
                "sql_id",
                "",
            )
            or ""
        ).strip()

        function_theme = str(
            self._record_value(
                record,
                "function_theme",
                "",
            )
            or ""
        ).strip()

        version = int(
            self._record_value(
                record,
                "version",
                1,
            )
            or 1
        )

        source_file = str(
            self._record_value(
                record,
                "source_file",
                "",
            )
            or "数据库知识库"
        ).strip()

        source_sheet = str(
            self._record_value(
                record,
                "source_sheet",
                "",
            )
            or "SQL知识表"
        ).strip()

        document = (
            self.build_sql_record_text(
                record
            )
        )
        retrieval_text = (
            self.build_sql_retrieval_text(
                record
            )
        )

        if not document.strip():
            raise ValueError(
                "SQL记录没有可写入向量库的内容。"
            )
        if not retrieval_text.strip():
            raise ValueError(
                "SQL记录没有可用于检索的功能主题。"
            )

        location = (
            f"工作表：{source_sheet}"
            f"｜SQL_ID：{sql_id}"
        )

        # 先删除旧向量，避免以前存在多个旧文本块
        self.delete_sql_record(
            int(record_id)
        )

        self.collection.upsert(
            ids=[
                self._sql_record_id(
                    int(record_id)
                )
            ],
            documents=[
                document
            ],
            metadatas=[
                {
                    "record_kind": (
                        "sql_record"
                    ),
                    "record_id": int(
                        record_id
                    ),
                    "record_version": (
                        version
                    ),
                    "sql_id": sql_id,
                    "function_theme": (
                        function_theme
                    ),
                    "source": source_file,
                    "location": location,
                    "worksheet": (
                        source_sheet
                    ),
                    "chunk_index": 0,
                }
            ],
            # 只使用功能主题生成向量，避免SQL正文、字段名、表名和备注干扰检索。
            embeddings=self._encode(
                [retrieval_text]
            ),
        )

    def clear_sql_records(self) -> None:
        """
        只清除数据库SQL记录对应的向量。

        不删除用户上传的普通PDF、Word等文档。
        """

        self.collection.delete(
            where={
                "record_kind": "sql_record"
            }
        )

    def rebuild_sql_records(
        self,
        records: list[Any],
    ) -> int:
        """根据数据库中的有效记录重建SQL向量。"""

        self.clear_sql_records()

        active_records = [
            record
            for record in records
            if self._record_value(
                record,
                "deleted_at",
                None,
            ) is None
        ]

        for record in active_records:
            self.upsert_sql_record(
                record
            )

        return len(active_records)

    # =====================================================
    # 检索辅助
    # =====================================================

    @staticmethod
    def _metadata_int(
        metadata: dict,
        field_name: str,
    ) -> int | None:
        value = metadata.get(
            field_name
        )

        if value is None:
            return None

        try:
            return int(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

    @classmethod
    def _build_search_result(
        cls,
        document: str,
        metadata: dict | None,
        distance: float | None,
        default_index: int,
    ) -> SearchResult:
        metadata = metadata or {}

        chunk_index = cls._metadata_int(
            metadata,
            "chunk_index",
        )

        if chunk_index is None:
            chunk_index = default_index

        return SearchResult(
            text=document,
            source=str(
                metadata.get(
                    "source",
                    "未知来源",
                )
            ),
            location=str(
                metadata.get(
                    "location",
                    "未知位置",
                )
            ),
            chunk_index=chunk_index,
            distance=(
                float(distance)
                if distance is not None
                else None
            ),
            record_id=cls._metadata_int(
                metadata,
                "record_id",
            ),
            sql_id=(
                str(metadata["sql_id"])
                if metadata.get("sql_id")
                is not None
                else None
            ),
            function_theme=(
                str(
                    metadata[
                        "function_theme"
                    ]
                )
                if metadata.get(
                    "function_theme"
                ) is not None
                else None
            ),
            record_version=cls._metadata_int(
                metadata,
                "record_version",
            ),
        )

    @staticmethod
    def _normalize_function_text(
        text: str,
    ) -> str:
        text = str(
            text
        ).strip().lower()

        prefix_patterns = [
            r"^(?:你好|您好)",
            (
                r"^(?:请问|麻烦问一下|"
                r"麻烦帮我|帮我|请帮我)"
            ),
            (
                r"^(?:我想知道|我想了解|"
                r"我想查询|我想查|"
                r"想知道|想了解)"
            ),
            (
                r"^(?:能不能|能否|"
                r"是否可以|可以)"
            ),
        ]

        changed = True

        while changed:
            original = text

            for pattern in prefix_patterns:
                text = re.sub(
                    pattern,
                    "",
                    text,
                ).strip()

            changed = text != original

        text = re.sub(
            r"^(?:怎么|如何|怎样)(?:对|把)?",
            "",
            text,
        )

        text = re.sub(
            (
                r"^(?:查询一下|查一下|查询|"
                r"查找|搜索|检索|查)"
            ),
            "",
            text,
        )

        text = re.sub(
            r"(?:怎么|如何|怎样)",
            "",
            text,
        )

        text = re.sub(
            r"^(?:对|把)",
            "",
            text,
        )

        text = re.sub(
            (
                r"[\s，。！？、；：:,.!?;"
                r"／/\\（）()【】\[\]《》"
                r"<>_\-—]+"
            ),
            "",
            text,
        )

        return text.replace(
            "的",
            "",
        )

    @staticmethod
    def _extract_function_theme(
        document: str,
    ) -> str | None:
        match = re.search(
            (
                r"(?im)^\s*功能主题"
                r"\s*[:：]\s*(.*?)\s*$"
            ),
            document,
        )

        if not match:
            return None

        function_theme = (
            match.group(1).strip()
        )

        return function_theme or None

    # =====================================================
    # 搜索
    # =====================================================
    def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        混合检索流程：

        1. 检查功能主题是否完全匹配；
        2. 获取功能主题文字匹配候选；
        3. 获取BGE向量检索候选；
        4. 合并并去重；
        5. 使用文字分数和向量分数联合排序；
        6. 返回前FINAL_CONTEXT_K条给Agent。
        """

        query = query.strip()

        if not query:
            return []

        collection_count = self.count()

        if collection_count == 0:
            return []

        # 最终交给DeepSeek的数量
        final_limit = min(
            (
                top_k
                or self.config.final_context_k
            ),
            collection_count,
        )

        # 本地初选候选数量
        candidate_limit = min(
            max(
                self.config.retrieval_candidate_k,
                final_limit,
            ),
            collection_count,
        )

        normalized_query = (
            self._normalize_function_text(
                query
            )
        )

        # =====================================================
        # 第一部分：读取带功能主题的记录
        # =====================================================
        stored_data = (
            self.collection.get(
                where={
                    "record_kind": (
                        "sql_record"
                    )
                },
                include=[
                    "documents",
                    "metadatas",
                ],
            )
        )

        stored_documents = (
            stored_data.get(
                "documents"
            )
            or []
        )

        stored_metadatas = (
            stored_data.get(
                "metadatas"
            )
            or []
        )

        lexical_candidates: list[
            tuple[float, SearchResult]
        ] = []

        exact_matches: list[
            SearchResult
        ] = []

        # =====================================================
        # 第二部分：计算功能主题文字相似度
        # =====================================================

        for index, document in enumerate(
            stored_documents
        ):
            if not document:
                continue
            metadata = (
                stored_metadatas[index]
                if index
                < len(stored_metadatas)
                else {}
            )

            # 优先读取结构化metadata，
            # 不从SQL正文中搜索功能名称
            function_theme = str(
                metadata.get(
                    "function_theme",
                    "",
                )
                or ""
            ).strip()

            # 兼容旧索引
            if not function_theme:
                function_theme = (
                    self._extract_function_theme(
                        document
                    )
                    or ""
                ).strip()

            if not function_theme:
                continue

            normalized_theme = (
                self._normalize_function_text(
                    function_theme
                )
            )

            if (
                not normalized_query
                or not normalized_theme
            ):
                continue

            if (
                normalized_query
                == normalized_theme
            ):
                theme_similarity = 1.0

            elif (
                len(normalized_query) >= 2
                and len(normalized_theme) >= 2
                and (
                    normalized_query
                    in normalized_theme
                    or normalized_theme
                    in normalized_query
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

                coverage = (
                    shorter_length
                    / longer_length
                )

                theme_similarity = (
                    0.90
                    + 0.09 * coverage
                )

            else:
                theme_similarity = (
                    SequenceMatcher(
                        None,
                        normalized_query,
                        normalized_theme,
                    ).ratio()
                )
            search_result = (
                self._build_search_result(
                    document=document,
                    metadata=metadata,
                    distance=(
                        1.0
                        - theme_similarity
                    ),
                    default_index=index,
                )
            )

            # 完全匹配单独保留
            if theme_similarity >= 0.999:
                exact_matches.append(
                    search_result
                )
                continue

            # 文字相似度过低的不进入文字候选
            if theme_similarity >= 0.55:
                lexical_candidates.append(
                    (
                        theme_similarity,
                        search_result,
                    )
                )

        # =====================================================
        # 第三部分：完全匹配优先
        # =====================================================

        if exact_matches:
            unique_exact_matches = []
            exact_seen_keys = set()

            for result in exact_matches:
                if result.record_id is not None:
                    result_key = (
                        "record",
                        result.record_id,
                    )

                else:
                    result_key = (
                        "document",
                        result.source,
                        result.location,
                        result.chunk_index,
                    )

                if result_key in exact_seen_keys:
                    continue

                exact_seen_keys.add(
                    result_key
                )

                unique_exact_matches.append(
                    result
                )

            def exact_sql_id_order(
                result: SearchResult,
            ) -> int:
                try:
                    return int(
                        result.sql_id or 0
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    return 0

            unique_exact_matches.sort(
                key=exact_sql_id_order
            )

            return unique_exact_matches[
                :final_limit
            ]

        # 功能主题候选按照相似度排序
        lexical_candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )
        # =====================================================
        # 高置信功能主题匹配
        # =====================================================

        if lexical_candidates:
            best_theme_similarity = (
                lexical_candidates[0][0]
            )

            # 包含关系等高置信功能匹配，
            # 直接按照功能主题返回，
            # 不允许SQL字段向量干扰。
            if best_theme_similarity >= 0.90:
                cutoff = max(
                    0.90,
                    best_theme_similarity - 0.02,
                )

                high_confidence_results = [
                    result
                    for similarity, result
                    in lexical_candidates
                    if similarity >= cutoff
                ]

                return high_confidence_results[
                    :final_limit
                ]

        lexical_candidates = (
            lexical_candidates[
                :candidate_limit
            ]
        )

        # =====================================================
        # 第四部分：BGE向量检索
        # =====================================================
        query_retrieval_text = (
            f"功能主题：{query}"
        )
        vector_result = (
            self.collection.query(
                query_embeddings=self._encode(
                    [query_retrieval_text]
                ),
                n_results=candidate_limit,
                where={
                    "record_kind": "sql_record"
                },
                include=[
                    "documents",
                    "metadatas",
                    "distances",
                ],
            )
        )

        vector_documents = (
            vector_result.get(
                "documents"
            )
            or [[]]
        )[0]

        vector_metadatas = (
            vector_result.get(
                "metadatas"
            )
            or [[]]
        )[0]

        vector_distances = (
            vector_result.get(
                "distances"
            )
            or [[]]
        )[0]

        vector_candidates: list[
            tuple[float, SearchResult]
        ] = []

        for index, document in enumerate(
            vector_documents
        ):
            if not document:
                continue

            metadata = (
                vector_metadatas[index]
                if index
                < len(vector_metadatas)
                else {}
            )

            distance = (
                vector_distances[index]
                if index
                < len(vector_distances)
                else None
            )

            search_result = (
                self._build_search_result(
                    document=document,
                    metadata=metadata,
                    distance=distance,
                    default_index=index,
                )
            )

            # 将距离转换为0到1之间的相似度。
            # 距离越小，相似度越高。
            if distance is None:
                vector_similarity = 0.0

            else:
                safe_distance = max(
                    float(distance),
                    0.0,
                )

                vector_similarity = (
                    1.0
                    / (
                        1.0
                        + safe_distance
                    )
                )

            vector_candidates.append(
                (
                    vector_similarity,
                    search_result,
                )
            )

        # =====================================================
        # 第五部分：合并功能主题与向量候选
        # =====================================================

        merged_candidates: dict[
            tuple,
            dict[str, object],
        ] = {}

        def build_result_key(
            result: SearchResult,
        ) -> tuple:
            """
            数据库记录优先使用稳定record_id去重。

            普通文档使用来源、位置和片段序号去重。
            """

            if result.record_id is not None:
                return (
                    "record",
                    result.record_id,
                )

            return (
                "document",
                result.source,
                result.location,
                result.chunk_index,
            )

        for (
            theme_similarity,
            result,
        ) in lexical_candidates:
            result_key = build_result_key(
                result
            )

            merged_candidates[
                result_key
            ] = {
                "result": result,
                "theme_similarity": (
                    theme_similarity
                ),
                "vector_similarity": 0.0,
            }

        for (
            vector_similarity,
            result,
        ) in vector_candidates:
            result_key = build_result_key(
                result
            )

            if (
                result_key
                not in merged_candidates
            ):
                merged_candidates[
                    result_key
                ] = {
                    "result": result,
                    "theme_similarity": 0.0,
                    "vector_similarity": (
                        vector_similarity
                    ),
                }

            else:
                merged_candidates[
                    result_key
                ][
                    "vector_similarity"
                ] = vector_similarity

                # 使用向量检索结果保存的distance
                merged_candidates[
                    result_key
                ]["result"] = result

        # =====================================================
        # 第六部分：联合打分和重新排序
        # =====================================================

        ranked_candidates: list[
            tuple[float, SearchResult]
        ] = []

        for candidate in (
            merged_candidates.values()
        ):
            result = candidate["result"]

            theme_similarity = float(
                candidate[
                    "theme_similarity"
                ]
            )

            vector_similarity = float(
                candidate[
                    "vector_similarity"
                ]
            )

            if (
                theme_similarity > 0
                and vector_similarity > 0
            ):
                # 同时被两种方法找到，可信度最高
                combined_score = (
                    0.60
                    * theme_similarity
                    + 0.40
                    * vector_similarity
                )

            elif theme_similarity > 0:
                # 只被功能主题检索到
                combined_score = (
                    0.90
                    * theme_similarity
                )

            else:
                # 只被向量检索到
                combined_score = (
                    0.90
                    * vector_similarity
                )

            # 功能主题达到较高相似度时增加奖励
            if theme_similarity >= 0.78:
                combined_score += 0.08

            ranked_candidates.append(
                (
                    combined_score,
                    result,
                )
            )

        ranked_candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            result
            for _, result
            in ranked_candidates[
                :final_limit
            ]
        ]
        
    # =====================================================
    # 数据库管理
    # =====================================================

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        """
        清空整个Chroma集合。

        该操作会删除：
        1. 数据库SQL向量；
        2. 普通上传文档向量。
        """

        self.client.delete_collection(
            self.config.collection_name
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=(
                    self.config.collection_name
                ),
                embedding_function=None,
            )
        )