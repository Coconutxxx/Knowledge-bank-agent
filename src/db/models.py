"""数据库表结构。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.db.database import Base


def utc_now() -> datetime:
    """返回带时区的UTC时间。"""

    return datetime.now(
        timezone.utc
    )


class User(Base):
    """系统用户。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="viewer",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    last_login_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class SQLRecord(Base):
    """SQL知识库记录。"""

    __tablename__ = "sql_records"

    # 永久稳定的数据库内部身份
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 当前知识库中的动态连续序号
    # 软删除记录会把该值设为None
    sql_id: Mapped[int | None] = mapped_column(
        Integer,
        unique=True,
        index=True,
        nullable=True,
    )

    # 记录在原始上传文件中的SQL_ID
    source_sql_id: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    # 记录在原始Excel中的行号
    source_row: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    business_domain: Mapped[
        str | None
    ] = mapped_column(
        String(200),
        nullable=True,
    )

    function_theme: Mapped[str] = mapped_column(
        String(500),
        index=True,
        nullable=False,
    )

    step: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    function_type: Mapped[
        str | None
    ] = mapped_column(
        String(200),
        nullable=True,
    )

    statement_type: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    source_tables: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    table_completeness: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    field_completeness: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    missing_tables: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    unregistered_fields: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    field_ownership_unknown: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    unexplained_fields: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    sql_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    notes: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    source_file: Mapped[
        str | None
    ] = mapped_column(
        String(500),
        nullable=True,
    )

    source_sheet: Mapped[
        str | None
    ] = mapped_column(
        String(500),
        nullable=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    created_by: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    updated_by: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    deleted_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditLog(Base):
    """系统操作日志。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    record_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey("sql_records.id"),
        nullable=True,
    )

    old_value: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    new_value: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class ImportBatch(Base):
    """Excel批量导入记录。"""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )

    import_mode: Mapped[str] = mapped_column(
        String(20),
        default="append",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    insert_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    update_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    unchanged_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    invalid_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    uploaded_by: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class VectorSyncJob(Base):
    """数据库与Chroma同步任务。"""

    __tablename__ = "vector_sync_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    record_id: Mapped[int] = mapped_column(
        ForeignKey("sql_records.id"),
        index=True,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
        nullable=False,
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )