"""SQL知识库CRUD测试。"""

from __future__ import annotations

from datetime import datetime
from getpass import getpass

from sqlalchemy import select

from src.auth.auth_service import (
    authenticate_user,
)
from src.db.database import (
    init_db,
    session_scope,
)
from src.db.models import (
    AuditLog,
    VectorSyncJob,
)
from src.services.knowledge_service import (
    KnowledgeService,
    SQLRecordData,
)


def main() -> None:
    init_db()

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

    print(
        f"登录成功：{current_user.username}，"
        f"角色：{current_user.role}"
    )

    service = KnowledgeService()

    unique_suffix = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    test_sql_id = (
        f"TEST-{unique_suffix}"
    )

    print("\n1. 测试新增")

    created = service.create_record(
        SQLRecordData(
            sql_id=test_sql_id,
            business_domain="测试业务域",
            function_theme="测试查询客户信息",
            step="1",
            function_type="测试功能",
            statement_type="SELECT",
            source_tables="test_customer",
            sql_text=(
                "SELECT customer_id, customer_name\n"
                "FROM test_customer;"
            ),
            notes="CRUD自动测试记录",
            source_file="crud_smoke_test.py",
            source_sheet="自动测试",
        ),
        current_user=current_user,
    )

    print(
        f"新增成功："
        f"id={created.id}，"
        f"SQL_ID={created.sql_id}，"
        f"version={created.version}"
    )

    print("\n2. 测试修改")

    updated = service.update_record(
        record_id=created.id,
        expected_version=created.version,
        data=SQLRecordData(
            sql_id=test_sql_id,
            business_domain="测试业务域",
            function_theme="测试查询客户详细信息",
            step="1",
            function_type="测试功能",
            statement_type="SELECT",
            source_tables="test_customer",
            sql_text=(
                "SELECT customer_id,\n"
                "       customer_name,\n"
                "       customer_type\n"
                "FROM test_customer;"
            ),
            notes="已经执行修改测试",
            source_file="crud_smoke_test.py",
            source_sheet="自动测试",
        ),
        current_user=current_user,
    )

    print(
        f"修改成功："
        f"id={updated.id}，"
        f"version={updated.version}"
    )

    print("\n3. 测试查询")

    search_results = service.list_records(
        current_user=current_user,
        keyword=test_sql_id,
    )

    print(
        f"查询到 {len(search_results)} 条记录。"
    )

    for record in search_results:
        print(
            f"- {record.sql_id}："
            f"{record.function_theme}"
        )

    print("\n4. 测试软删除")

    deleted = service.delete_record(
        record_id=created.id,
        current_user=current_user,
    )

    print(
        f"删除成功："
        f"deleted_at={deleted.deleted_at}"
    )

    print("\n5. 检查操作日志和同步任务")

    with session_scope() as session:
        audit_logs = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.record_id
                    == created.id
                )
            ).all()
        )

        sync_jobs = list(
            session.scalars(
                select(VectorSyncJob).where(
                    VectorSyncJob.record_id
                    == created.id
                )
            ).all()
        )

    print(
        "操作日志：",
        [
            log.action
            for log in audit_logs
        ],
    )

    print(
        "向量同步任务：",
        [
            f"{job.action}:{job.status}"
            for job in sync_jobs
        ],
    )

    print("\nCRUD测试完成。")


if __name__ == "__main__":
    main()