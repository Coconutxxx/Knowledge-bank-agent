"""数据库与Chroma同步测试。"""

from __future__ import annotations

from datetime import datetime
from getpass import getpass

from src.auth.auth_service import (
    authenticate_user,
)
from src.rag.vector_store import (
    VectorStore,
)
from src.services.knowledge_service import (
    KnowledgeService,
    SQLRecordData,
)
from src.services.vector_sync_service import (
    VectorSyncService,
)


def main() -> None:
    username = input(
        "管理员用户名："
    ).strip()

    password = getpass(
        "管理员密码："
    )

    current_user = authenticate_user(
        username,
        password,
    )

    if current_user is None:
        print("登录失败。")
        return

    knowledge_service = (
        KnowledgeService()
    )

    store = VectorStore()

    sync_service = VectorSyncService(
        store=store
    )

    suffix = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    sql_id = f"VECTOR-TEST-{suffix}"

    print("\n1. 创建数据库记录")

    created = (
        knowledge_service.create_record(
            SQLRecordData(
                sql_id=sql_id,
                business_domain="向量同步测试",
                function_theme=(
                    "查询向量同步测试客户"
                ),
                statement_type="SELECT",
                source_tables=(
                    "test_vector_customer"
                ),
                sql_text=(
                    "SELECT customer_id,\n"
                    "       customer_name\n"
                    "FROM test_vector_customer;"
                ),
                notes="向量同步自动测试",
                source_file=(
                    "vector_sync_test.py"
                ),
                source_sheet="同步测试",
            ),
            current_user=current_user,
        )
    )

    print(
        f"数据库新增成功："
        f"record_id={created.id}"
    )

    print("\n2. 处理UPSERT同步任务")

    sync_result = (
        sync_service.process_pending()
    )

    print(sync_result)

    print("\n3. 检查Chroma记录")

    chroma_result = (
        store.collection.get(
            where={
                "record_id": created.id
            },
            include=[
                "documents",
                "metadatas",
            ],
        )
    )

    print(
        "Chroma记录数：",
        len(
            chroma_result.get(
                "ids",
                [],
            )
        ),
    )

    documents = (
        chroma_result.get(
            "documents",
            [],
        )
    )

    if documents:
        print("Chroma文本：")
        print(documents[0][:500])

    print("\n4. 测试检索")

    search_results = store.search(
        "怎么查询向量同步测试客户",
        top_k=3,
    )

    for result in search_results:
        print(
            f"record_id={result.record_id}，"
            f"sql_id={result.sql_id}，"
            f"distance={result.distance}"
        )

    print("\n5. 软删除数据库记录")

    knowledge_service.delete_record(
        record_id=created.id,
        current_user=current_user,
    )

    print("\n6. 处理DELETE同步任务")

    delete_sync_result = (
        sync_service.process_pending()
    )

    print(delete_sync_result)

    deleted_chroma_result = (
        store.collection.get(
            where={
                "record_id": created.id
            },
            include=[
                "documents",
            ],
        )
    )

    remaining_count = len(
        deleted_chroma_result.get(
            "ids",
            [],
        )
    )

    print(
        "删除后Chroma记录数：",
        remaining_count,
    )

    if remaining_count == 0:
        print(
            "\n数据库与Chroma同步测试成功。"
        )
    else:
        print(
            "\n同步测试失败："
            "Chroma中仍然存在记录。"
        )


if __name__ == "__main__":
    main()