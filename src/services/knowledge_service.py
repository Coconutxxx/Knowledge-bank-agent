"""SQL知识库增删改查业务逻辑。"""

from __future__ import annotations

import json
from dataclasses import (
    asdict,
    dataclass,
)

from src.auth.auth_service import (
    AuthenticatedUser,
    require_role,
)
from src.db.database import session_scope
from src.db.models import (
    SQLRecord,
    utc_now,
)
from src.db.repositories import (
    AuditLogRepository,
    SQLRecordRepository,
    VectorSyncJobRepository,
)


@dataclass(frozen=True)
class SQLRecordData:
    """新增或修改SQL记录的数据。"""

    function_theme: str
    sql_text: str

    source_sql_id: str | None = None
    source_row: int | None = None
    business_domain: str | None = None
    step: str | None = None
    function_type: str | None = None
    statement_type: str | None = None
    source_tables: str | None = None
    table_completeness: str | None = None
    field_completeness: str | None = None
    missing_tables: str | None = None
    unregistered_fields: str | None = None
    field_ownership_unknown: str | None = None
    unexplained_fields: str | None = None
    notes: str | None = None
    source_file: str | None = None
    source_sheet: str | None = None


@dataclass(frozen=True)
class SQLRecordView:
    """返回给页面使用的SQL记录。"""

    id: int
    sql_id: int | None
    source_sql_id: str | None
    source_row: int | None
    business_domain: str | None
    function_theme: str
    step: str | None
    function_type: str | None
    statement_type: str | None
    source_tables: str | None
    table_completeness: str | None
    field_completeness: str | None
    missing_tables: str | None
    unregistered_fields: str | None
    field_ownership_unknown: str | None
    unexplained_fields: str | None
    sql_text: str
    notes: str | None
    source_file: str | None
    source_sheet: str | None
    version: int
    created_by: int | None
    updated_by: int | None
    created_at: str
    updated_at: str
    deleted_at: str | None


def _clean_required(
    value: str,
    field_name: str,
) -> str:
    cleaned = str(value).strip()

    if not cleaned:
        raise ValueError(
            f"{field_name}不能为空。"
        )

    return cleaned


def _clean_optional(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()

    return cleaned or None


def _validate_data(
    data: SQLRecordData,
) -> SQLRecordData:
    function_theme = _clean_required(
        data.function_theme,
        "功能主题",
    )

    sql_text = _clean_required(
        data.sql_text,
        "SQL正文",
    )

    source_row = data.source_row

    if (
        source_row is not None
        and source_row <= 0
    ):
        source_row = None

    return SQLRecordData(
        function_theme=function_theme,
        sql_text=sql_text,
        source_sql_id=_clean_optional(
            data.source_sql_id
        ),
        source_row=source_row,
        business_domain=_clean_optional(
            data.business_domain
        ),
        step=_clean_optional(data.step),
        function_type=_clean_optional(
            data.function_type
        ),
        statement_type=_clean_optional(
            data.statement_type
        ),
        source_tables=_clean_optional(
            data.source_tables
        ),
        table_completeness=_clean_optional(
            data.table_completeness
        ),
        field_completeness=_clean_optional(
            data.field_completeness
        ),
        missing_tables=_clean_optional(
            data.missing_tables
        ),
        unregistered_fields=_clean_optional(
            data.unregistered_fields
        ),
        field_ownership_unknown=_clean_optional(
            data.field_ownership_unknown
        ),
        unexplained_fields=_clean_optional(
            data.unexplained_fields
        ),
        notes=_clean_optional(data.notes),
        source_file=_clean_optional(
            data.source_file
        ),
        source_sheet=_clean_optional(
            data.source_sheet
        ),
    )


def _record_to_view(
    record: SQLRecord,
) -> SQLRecordView:
    return SQLRecordView(
        id=record.id,
        sql_id=record.sql_id,
        source_sql_id=record.source_sql_id,
        source_row=record.source_row,
        business_domain=record.business_domain,
        function_theme=record.function_theme,
        step=record.step,
        function_type=record.function_type,
        statement_type=record.statement_type,
        source_tables=record.source_tables,
        table_completeness=(
            record.table_completeness
        ),
        field_completeness=(
            record.field_completeness
        ),
        missing_tables=record.missing_tables,
        unregistered_fields=(
            record.unregistered_fields
        ),
        field_ownership_unknown=(
            record.field_ownership_unknown
        ),
        unexplained_fields=(
            record.unexplained_fields
        ),
        sql_text=record.sql_text,
        notes=record.notes,
        source_file=record.source_file,
        source_sheet=record.source_sheet,
        version=record.version,
        created_by=record.created_by,
        updated_by=record.updated_by,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        deleted_at=(
            record.deleted_at.isoformat()
            if record.deleted_at
            else None
        ),
    )


def _view_json(
    view: SQLRecordView | None,
) -> str | None:
    if view is None:
        return None

    return json.dumps(
        asdict(view),
        ensure_ascii=False,
        sort_keys=True,
    )


def _apply_data(
    record: SQLRecord,
    data: SQLRecordData,
) -> None:
    record.source_sql_id = data.source_sql_id
    record.source_row = data.source_row
    record.business_domain = (
        data.business_domain
    )
    record.function_theme = (
        data.function_theme
    )
    record.step = data.step
    record.function_type = data.function_type
    record.statement_type = (
        data.statement_type
    )
    record.source_tables = data.source_tables
    record.table_completeness = (
        data.table_completeness
    )
    record.field_completeness = (
        data.field_completeness
    )
    record.missing_tables = (
        data.missing_tables
    )
    record.unregistered_fields = (
        data.unregistered_fields
    )
    record.field_ownership_unknown = (
        data.field_ownership_unknown
    )
    record.unexplained_fields = (
        data.unexplained_fields
    )
    record.sql_text = data.sql_text
    record.notes = data.notes
    record.source_file = data.source_file
    record.source_sheet = data.source_sheet


class KnowledgeService:
    """SQL知识记录业务服务。"""

    def __init__(self) -> None:
        self.records = SQLRecordRepository()
        self.audit_logs = AuditLogRepository()
        self.sync_jobs = (
            VectorSyncJobRepository()
        )

    def list_records(
        self,
        current_user: AuthenticatedUser,
        keyword: str = "",
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SQLRecordView]:
        require_role(
            current_user,
            "viewer",
            "editor",
            "admin",
        )

        if (
            include_deleted
            and current_user.role != "admin"
        ):
            raise PermissionError(
                "只有管理员可以查看已删除记录。"
            )

        with session_scope() as session:
            records = self.records.list_records(
                session,
                keyword=keyword,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
            )

            return [
                _record_to_view(record)
                for record in records
            ]

    def count_active_records(
        self,
        current_user: AuthenticatedUser,
        include_deleted: bool = False,
    ) -> int:
        require_role(
            current_user,
            "viewer",
            "editor",
            "admin",
        )

        if (
            include_deleted
            and current_user.role != "admin"
        ):
            raise PermissionError(
                "只有管理员可以查看已删除记录。"
            )

        with session_scope() as session:
            return self.records.count_records(
                session,
                include_deleted=include_deleted,
            )

    def get_record(
        self,
        record_id: int,
        current_user: AuthenticatedUser,
        include_deleted: bool = False,
    ) -> SQLRecordView:
        require_role(
            current_user,
            "viewer",
            "editor",
            "admin",
        )
        if (
            include_deleted
            and current_user.role != "admin"
        ):
            raise PermissionError(
                "只有管理员可以查看已删除记录。"
            )

        with session_scope() as session:
            record = self.records.get_by_id(
                session,
                record_id,
                include_deleted=include_deleted,
            )

            if record is None:
                raise ValueError(
                    "没有找到对应的SQL记录。"
                )

            return _record_to_view(record)

    def create_record(
        self,
        data: SQLRecordData,
        current_user: AuthenticatedUser,
    ) -> SQLRecordView:
        require_role(
            current_user,
            "editor",
            "admin",
        )

        clean_data = _validate_data(data)

        with session_scope() as session:
            next_sql_id = (
                self.records.get_max_sql_id(
                    session
                )
                + 1
            )

            record = SQLRecord(
                sql_id=next_sql_id,
                version=1,
                created_by=current_user.id,
                updated_by=current_user.id,
            )

            _apply_data(
                record,
                clean_data,
            )

            self.records.add(
                session,
                record,
            )

            created_view = _record_to_view(record)

            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="CREATE",
                record_id=record.id,
                old_value=None,
                new_value=_view_json(
                    created_view
                ),
            )

            self.sync_jobs.create(
                session,
                record_id=record.id,
                action="UPSERT",
            )

            return created_view

    def update_record(
        self,
        record_id: int,
        data: SQLRecordData,
        expected_version: int,
        current_user: AuthenticatedUser,
    ) -> SQLRecordView:
        require_role(
            current_user,
            "editor",
            "admin",
        )

        clean_data = _validate_data(data)

        with session_scope() as session:
            record = self.records.get_by_id(
                session,
                record_id,
            )

            if record is None:
                raise ValueError(
                    "没有找到需要修改的记录。"
                )

            if record.version != expected_version:
                raise ValueError(
                    "该记录已经被其他用户修改，"
                    "请重新加载后再编辑。"
                )

            old_view = _record_to_view(record)

            _apply_data(
                record,
                clean_data,
            )

            record.version += 1
            record.updated_by = current_user.id
            record.updated_at = utc_now()

            session.flush()

            new_view = _record_to_view(record)

            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="UPDATE",
                record_id=record.id,
                old_value=_view_json(old_view),
                new_value=_view_json(new_view),
            )

            self.sync_jobs.create(
                session,
                record_id=record.id,
                action="UPSERT",
            )

            return new_view

    def delete_record(
        self,
        record_id: int,
        current_user: AuthenticatedUser,
    ) -> SQLRecordView:
        require_role(
            current_user,
            "admin",
        )

        with session_scope() as session:
            record = self.records.get_by_id(
                session,
                record_id,
            )

            if record is None:
                raise ValueError(
                    "没有找到需要删除的记录。"
                )

            if record.sql_id is None:
                raise ValueError(
                    "该记录已经被删除。"
                )

            deleted_sql_id = record.sql_id
            old_view = _record_to_view(record)

            affected_records = (
                self.records.list_after_sql_id(
                    session,
                    deleted_sql_id,
                )
            )

            old_id_mapping = {
                item.id: item.sql_id
                for item in affected_records
            }

            # 先释放被删除记录占用的SQL_ID
            record.sql_id = None
            record.deleted_at = utc_now()
            record.updated_at = utc_now()
            record.updated_by = current_user.id
            record.version += 1

            session.flush()

            # 两阶段移动，避免唯一约束冲突
            if affected_records:
                max_sql_id = (
                    self.records.get_max_sql_id(
                        session
                    )
                )

                temporary_offset = (
                    max_sql_id
                    + len(affected_records)
                    + 1000
                )

                for item in affected_records:
                    item.sql_id = (
                        int(item.sql_id)
                        + temporary_offset
                    )

                session.flush()

                for item in affected_records:
                    item.sql_id = (
                        int(item.sql_id)
                        - temporary_offset
                        - 1
                    )
                    item.version += 1
                    item.updated_at = utc_now()
                    item.updated_by = (
                        current_user.id
                    )

                session.flush()

            deleted_view = _record_to_view(record)

            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="DELETE",
                record_id=record.id,
                old_value=_view_json(old_view),
                new_value=_view_json(
                    deleted_view
                ),
            )

            self.sync_jobs.create(
                session,
                record_id=record.id,
                action="DELETE",
            )

            if affected_records:
                changes = [
                    {
                        "record_id": item.id,
                        "old_sql_id": (
                            old_id_mapping[item.id]
                        ),
                        "new_sql_id": item.sql_id,
                    }
                    for item in affected_records
                ]

                self.audit_logs.create(
                    session,
                    user_id=current_user.id,
                    action="RESEQUENCE",
                    record_id=None,
                    old_value=None,
                    new_value=json.dumps(
                        changes,
                        ensure_ascii=False,
                    ),
                )

                for item in affected_records:
                    self.sync_jobs.create(
                        session,
                        record_id=item.id,
                        action="UPSERT",
                    )

            return deleted_view

    def restore_record(
        self,
        record_id: int,
        current_user: AuthenticatedUser,
    ) -> SQLRecordView:
        require_role(
            current_user,
            "admin",
        )

        with session_scope() as session:
            record = self.records.get_by_id(
                session,
                record_id,
                include_deleted=True,
            )

            if record is None:
                raise ValueError(
                    "没有找到需要恢复的记录。"
                )

            if record.deleted_at is None:
                raise ValueError(
                    "该记录没有被删除。"
                )

            old_view = _record_to_view(record)

            record.sql_id = (
                self.records.get_max_sql_id(
                    session
                )
                + 1
            )
            record.deleted_at = None
            record.version += 1
            record.updated_at = utc_now()
            record.updated_by = current_user.id

            session.flush()

            restored_view = _record_to_view(
                record
            )

            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="RESTORE",
                record_id=record.id,
                old_value=_view_json(old_view),
                new_value=_view_json(
                    restored_view
                ),
            )

            self.sync_jobs.create(
                session,
                record_id=record.id,
                action="UPSERT",
            )

            return restored_view