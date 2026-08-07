"""关系数据库与Chroma向量库同步。"""

from __future__ import annotations

from sqlalchemy import select

from src.db.database import (
    session_scope,
)
from src.db.models import (
    SQLRecord,
    VectorSyncJob,
    utc_now,
)
from src.rag.vector_store import (
    VectorStore,
)


class VectorSyncService:
    """处理待同步的向量任务。"""

    def __init__(
        self,
        store: VectorStore | None = None,
    ):
        self.store = (
            store or VectorStore()
        )

    def process_job(
        self,
        job_id: int,
    ) -> bool:
        """
        处理单条同步任务。

        成功返回True；
        失败返回False。
        """

        with session_scope() as session:
            job = session.get(
                VectorSyncJob,
                job_id,
            )

            if job is None:
                return False

            if job.status == "success":
                return True

            record = session.get(
                SQLRecord,
                job.record_id,
            )

            try:
                if job.action == "DELETE":
                    self.store.delete_sql_record(
                        job.record_id
                    )

                elif job.action == "UPSERT":
                    if (
                        record is None
                        or record.deleted_at
                        is not None
                    ):
                        self.store.delete_sql_record(
                            job.record_id
                        )

                    else:
                        self.store.upsert_sql_record(
                            record
                        )

                else:
                    raise ValueError(
                        f"不支持的同步动作："
                        f"{job.action}"
                    )

                job.status = "success"
                job.error_message = None
                job.completed_at = utc_now()

                return True

            except Exception as exc:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = utc_now()

                return False

    def process_pending(
        self,
        limit: int = 100,
    ) -> dict[str, int]:
        """批量处理等待同步的任务。"""

        with session_scope() as session:
            job_ids = list(
                session.scalars(
                    select(
                        VectorSyncJob.id
                    )
                    .where(
                        VectorSyncJob.status
                        == "pending"
                    )
                    .order_by(
                        VectorSyncJob.id.asc()
                    )
                    .limit(
                        max(
                            1,
                            min(limit, 1000),
                        )
                    )
                ).all()
            )

        success_count = 0
        failed_count = 0

        for job_id in job_ids:
            success = self.process_job(
                job_id
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

        return {
            "total": len(job_ids),
            "success": success_count,
            "failed": failed_count,
        }

    def retry_failed(
        self,
    ) -> int:
        """把失败任务重新设为等待处理。"""

        with session_scope() as session:
            failed_jobs = list(
                session.scalars(
                    select(
                        VectorSyncJob
                    ).where(
                        VectorSyncJob.status
                        == "failed"
                    )
                ).all()
            )

            for job in failed_jobs:
                job.status = "pending"
                job.error_message = None
                job.completed_at = None

            return len(failed_jobs)

    def rebuild_all(
        self,
    ) -> int:
        """
        根据关系数据库中的所有有效SQL记录
        重建SQL向量索引。
        """

        with session_scope() as session:
            records = list(
                session.scalars(
                    select(
                        SQLRecord
                    )
                    .where(
                        SQLRecord.deleted_at
                        .is_(None)
                    )
                    .order_by(
                        SQLRecord.id.asc()
                    )
                ).all()
            )

        return self.store.rebuild_sql_records(
            records
        )


def main() -> None:
    service = VectorSyncService()

    result = service.process_pending()

    print("向量同步完成。")
    print(f"待处理任务：{result['total']}")
    print(f"同步成功：{result['success']}")
    print(f"同步失败：{result['failed']}")


if __name__ == "__main__":
    main()