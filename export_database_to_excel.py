"""从数据库导出SQL知识库Excel。"""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

from src.auth.auth_service import (
    authenticate_user,
)
from src.services.export_service import (
    ExportService,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "从数据库导出最新版SQL知识库"
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="data/exports",
        help=(
            "导出目录，"
            "默认data/exports"
        ),
    )

    arguments = parser.parse_args()

    username = input(
        "用户名："
    ).strip()

    password = getpass(
        "密码："
    )

    current_user = authenticate_user(
        username,
        password,
    )

    if current_user is None:
        print("登录失败。")
        return

    print(
        f"登录成功："
        f"{current_user.username}，"
        f"角色：{current_user.role}"
    )

    export_service = (
        ExportService()
    )

    result = (
        export_service
        .export_sql_records(
            current_user=current_user
        )
    )

    output_directory = Path(
        arguments.output_dir
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_directory
        / result.file_name
    )

    output_path.write_bytes(
        result.data
    )

    print("导出成功。")
    print(
        f"SQL记录数："
        f"{result.record_count}"
    )
    print(
        f"文件路径："
        f"{output_path.resolve()}"
    )


if __name__ == "__main__":
    main()