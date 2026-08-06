from __future__ import annotations

from getpass import getpass

from src.auth.auth_service import (
    admin_exists,
    create_user,
    username_exists,
)


def main() -> None:
    print("=" * 40)
    print("初始化系统管理员")
    print("=" * 40)

    if admin_exists():
        print(
            "系统中已经存在管理员账号。"
        )
        print(
            "为避免绕过权限控制，"
            "初始化脚本不允许继续创建管理员。"
        )
        return

    while True:
        username = input(
            "请输入管理员用户名："
        ).strip()

        if not username:
            print(
                "用户名不能为空，请重新输入。"
            )
            continue

        try:
            if username_exists(username):
                print(
                    f"用户名 {username!r} 已存在，"
                    "请更换用户名。"
                )
                continue

        except ValueError as exc:
            print(
                f"用户名格式错误：{exc}"
            )
            continue

        break

    while True:
        print(
            "输入密码时终端不会显示字符，"
            "这是正常现象。"
        )

        password = getpass(
            "请输入管理员密码："
        )

        confirm_password = getpass(
            "请再次输入管理员密码："
        )

        if not password:
            print(
                "密码不能为空，请重新输入。"
            )
            continue

        if password != confirm_password:
            print(
                "两次密码不一致，请重新输入。"
            )
            continue

        break

    try:
        user = create_user(
            username=username,
            password=password,
            role="admin",
        )

    except Exception as exc:
        print(
            f"管理员创建失败：{exc}"
        )
        return

    print()
    print("系统管理员创建成功。")
    print(f"用户ID：{user.id}")
    print(f"用户名：{user.username}")
    print(f"角色：{user.role}")


if __name__ == "__main__":
    main()