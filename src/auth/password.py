"""密码加密与验证。"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
)


password_hasher = PasswordHasher()


def validate_password_strength(
    password: str,
) -> None:
    """
    检查密码是否满足基础要求。

    当前要求：
    1. 不能为空；
    2. 至少8位；
    3. 最多128位；
    4. 不能全是空格。
    """

    if not password:
        raise ValueError(
            "密码不能为空。"
        )

    if not password.strip():
        raise ValueError(
            "密码不能全部为空格。"
        )

    if len(password) < 8:
        raise ValueError(
            "密码至少需要8个字符。"
        )

    if len(password) > 128:
        raise ValueError(
            "密码不能超过128个字符。"
        )


def hash_password(
    password: str,
) -> str:
    """将明文密码转换成Argon2哈希。"""

    validate_password_strength(
        password
    )

    return password_hasher.hash(
        password
    )


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """验证明文密码是否与哈希一致。"""

    if not password:
        return False

    if not password_hash:
        return False

    try:
        return bool(
            password_hasher.verify(
                password_hash,
                password,
            )
        )

    except (
        VerificationError,
        InvalidHashError,
    ):
        return False


def password_needs_rehash(
    password_hash: str,
) -> bool:
    """
    检查旧密码哈希是否需要升级。

    如果Argon2默认参数以后发生变化，
    用户登录成功后可以自动更新密码哈希。
    """

    if not password_hash:
        return True

    try:
        return password_hasher.check_needs_rehash(
            password_hash
        )

    except InvalidHashError:
        return True