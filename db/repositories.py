"""数据库仓储层。"""

from __future__ import annotations

from sqlalchemy import (
    func,
    or_,
    select,
)
from sqlalchemy.orm import Session

from src.db.models import (
    AuditLog,
    SQLRecord,
    VectorSyncJob,
)


class SQLRecordRepository:
    """SQL知识记录数据库操作。"""

    @staticmethod
    def get_by_id(
        session: Session,
        record_id: int,
        include_deleted: bool = False,
    ) -> SQLRecord | None:
        statement = select(
            SQLRecord
        ).where(
            SQLRecord.id == record_id
        )

        if not include_deleted:
            statement = statement.where(
                SQLRecord.deleted_at.is_(None)
            )

        return session.scalar(statement)

    @staticmethod
    def get_by_sql_id(
        session: Session,
        sql_id: int,
    ) -> SQLRecord | None:
        return session.scalar(
            select(SQLRecord).where(
                SQLRecord.sql_id == sql_id,
                SQLRecord.deleted_at.is_(None),
            )
        )

    @staticmethod
    def get_max_sql_id(
        session: Session,
    ) -> int:
        value = session.scalar(
            select(
                func.max(SQLRecord.sql_id)
            ).where(
                SQLRecord.deleted_at.is_(None)
            )
        )

        return int(value or 0)

    @staticmethod
    def list_after_sql_id(
        session: Session,
        sql_id: int,
    ) -> list[SQLRecord]:
        return list(
            session.scalars(
                select(SQLRecord)
                .where(
                    SQLRecord.deleted_at.is_(None),
                    SQLRecord.sql_id > sql_id,
                )
                .order_by(
                    SQLRecord.sql_id.asc()
                )
            ).all()
        )

    @staticmethod
    def list_records(
        session: Session,
        keyword: str = "",
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SQLRecord]:
        statement = select(SQLRecord)

        if not include_deleted:
            statement = statement.where(
                SQLRecord.deleted_at.is_(None)
            )

        keyword = keyword.strip()

        if keyword:
            conditions = [
                SQLRecord.function_theme.ilike(
                    f"%{keyword}%"
                ),
                SQLRecord.business_domain.ilike(
                    f"%{keyword}%"
                ),
                SQLRecord.source_tables.ilike(
                    f"%{keyword}%"
                ),
                SQLRecord.sql_text.ilike(
                    f"%{keyword}%"
                ),
                SQLRecord.source_sql_id.ilike(
                    f"%{keyword}%"
                ),
            ]

            if keyword.isdigit():
                conditions.append(
                    SQLRecord.sql_id
                    == int(keyword)
                )

            statement = statement.where(
                or_(*conditions)
            )

        statement = (
            statement
            .order_by(
                SQLRecord.sql_id.asc(),
                SQLRecord.id.asc(),
            )
            .offset(max(offset, 0))
            .limit(max(1, min(limit, 1000)))
        )

        return list(
            session.scalars(statement).all()
        )

    @staticmethod
    def count_records(
        session: Session,
        include_deleted: bool = False,
    ) -> int:
        statement = select(
            func.count(SQLRecord.id)
        )

        if not include_deleted:
            statement = statement.where(
                SQLRecord.deleted_at.is_(None)
            )

        return int(
            session.scalar(statement) or 0
        )

    @staticmethod
    def add(
        session: Session,
        record: SQLRecord,
    ) -> SQLRecord:
        session.add(record)
        session.flush()

        return record


class AuditLogRepository:
    """操作日志数据库操作。"""

    @staticmethod
    def create(
        session: Session,
        *,
        user_id: int | None,
        action: str,
        record_id: int | None,
        old_value: str | None,
        new_value: str | None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            record_id=record_id,
            old_value=old_value,
            new_value=new_value,
        )

        session.add(log)
        session.flush()

        return log


class VectorSyncJobRepository:
    """向量同步任务数据库操作。"""

    @staticmethod
    def create(
        session: Session,
        *,
        record_id: int,
        action: str,
    ) -> VectorSyncJob:
        job = VectorSyncJob(
            record_id=record_id,
            action=action,
            status="pending",
        )

        session.add(job)
        session.flush()

        return job