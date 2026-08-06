from __future__ import annotations

from getpass import getpass

from src.auth.auth_service import (
    create_user,
    username_exists,
)


ROLE_NAMES = {
    "1": "viewer",
    "2": "editor",
}


def input_new_username() -> str:
    """
    循环输入用户名，直到用户名格式正确且没有重复。
    """

    while True:
        username = input(
            "请输入用户名："
        ).strip()

        if not username:
            print(
                "用户名不能为空，请重新输入。\n"
            )
            continue

        try:
            exists = username_exists(
                username
            )

        except ValueError as exc:
            print(
                f"用户名格式错误：{exc}\n"
            )
            continue

        if exists:
            print(
                f"用户名 {username!r} 已经存在，"
                "请更换一个用户名。\n"
            )
            continue

        return username


def input_role() -> str:
    """
    创建普通系统用户。
    管理员账号不能通过本脚本创建。
    """
    while True:
        print()
        print("请选择用户角色：")
        print("1. viewer：只能查看和问答")
        print("2. editor：可以新增和修改")

        role_choice = input(
            "请输入角色序号 [1/2]："
        ).strip()

        role = ROLE_NAMES.get(
            role_choice
        )

        if role is not None:
            return role

        print(
            "角色序号错误，请重新选择。"
        )


def input_password() -> str:
    """
    循环输入密码，直到两次密码一致。
    """

    while True:
        print()
        print(
            "输入密码时终端不会显示字符，"
            "这是正常现象。\n"
        )
        print(
            "密码最少需要8个字符。"
        )
        password = getpass(
            "请输入密码："
        )

        confirm_password = getpass(
            "请再次输入密码："
        )

        if not password:
            print(
                "密码不能为空，请重新输入。"
            )
            continue

        if password != confirm_password:
            print(
                "两次输入的密码不一致，"
                "请重新输入。"
            )
            continue

        return password


def main() -> None:
    print("=" * 40)
    print("创建知识库系统普通用户")
    print("=" * 40)    
    print("用户名至少需要3个字符，只能使用英文字母、数字、下划线、短横线和英文句点")
    print("=" * 40)
    username = input_new_username()
    role = input_role()
    password = input_password()

    try:
        user = create_user(
            username=username,
            password=password,
            role=role,
        )

    except ValueError as exc:
        # create_user内部仍会再次检查重复用户名，
        # 防止检查后其他人恰好创建了同名账号。
        print()
        print(f"创建失败：{exc}")
        return

    except Exception as exc:
        print()
        print(
            f"创建用户时出现异常：{exc}"
        )
        return

    print()
    print("=" * 40)
    print("用户创建成功")
    print("=" * 40)
    print(f"用户ID：{user.id}")
    print(f"用户名：{user.username}")
    print(f"用户角色：{user.role}")


if __name__ == "__main__":
    main()


