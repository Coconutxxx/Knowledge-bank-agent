"""初始化数据库表。"""

from __future__ import annotations

from sqlalchemy import inspect

from src.db.database import (
    engine,
    init_db,
)


def main() -> None:
    init_db()

    inspector = inspect(engine)

    table_names = sorted(
        inspector.get_table_names()
    )

    print("数据库初始化成功。")
    print("已创建数据表：")

    for table_name in table_names:
        print(f"- {table_name}")


if __name__ == "__main__":
    main()