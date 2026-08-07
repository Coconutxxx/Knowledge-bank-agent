"""数据库连接、会话和初始化。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from src.config import settings


def _prepare_sqlite_directory(
    database_url: str,
) -> None:
    """
    如果使用SQLite，提前创建数据库文件所在目录。

    例如：
    sqlite:///./storage/knowledge.db
    会创建：
    storage/
    """

    sqlite_prefix = "sqlite:///"

    if not database_url.startswith(sqlite_prefix):
        return

    database_path = database_url.removeprefix(
        sqlite_prefix
    )

    if database_path in {
        "",
        ":memory:",
    }:
        return

    Path(database_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )


_prepare_sqlite_directory(
    settings.database_url
)


connect_args: dict = {}

if settings.database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }


engine: Engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(
        engine,
        "connect",
    )
    def enable_sqlite_foreign_keys(
        dbapi_connection,
        connection_record,
    ) -> None:
        """
        SQLite默认可能不启用外键检查，
        每次连接时主动打开。
        """

        del connection_record

        cursor = dbapi_connection.cursor()

        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )

        cursor.close()


class Base(DeclarativeBase):
    """所有数据库模型的基类。"""

    pass


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    提供数据库事务。

    正常执行时提交；
    出现异常时回滚；
    最后自动关闭连接。
    """

    session = SessionLocal()

    try:
        yield session

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def init_db() -> None:
    """创建当前尚不存在的数据库表。"""

    # 必须导入models，
    # SQLAlchemy才能知道有哪些表需要创建。
    from src.db import models

    del models

    Base.metadata.create_all(
        bind=engine
    )