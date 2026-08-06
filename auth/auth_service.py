"""用户创建、登录验证和角色判断。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.auth.password import (
    hash_password,
    password_needs_rehash,
    verify_password,
)
from src.db.database import session_scope
from src.db.models import (
    User,
    utc_now,
)


VALID_ROLES = {
    "viewer",
    "editor",
    "admin",
}


@dataclass(frozen=True)
class AuthenticatedUser:
    """
    登录成功后返回给页面使用的用户信息。

    不直接把SQLAlchemy的User对象放入
    st.session_state，避免数据库会话关闭后出错。
    """

    id: int
    username: str
    role: str
    is_active: bool


def normalize_username(
    username: str,
) -> str:
    """
    统一用户名格式。

    例如：
        Admin
        ADMIN
        admin

    最终都会保存为：
        admin
    """

    return username.strip().lower()


def validate_username(
    username: str,
) -> str:
    """检查并返回标准化用户名。"""

    normalized = normalize_username(
        username
    )

    if not normalized:
        raise ValueError(
            "用户名不能为空。"
        )

    if len(normalized) < 3:
        raise ValueError(
            "用户名至少需要3个字符。"
        )

    if len(normalized) > 100:
        raise ValueError(
            "用户名不能超过100个字符。"
        )

    allowed_characters = set(
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789"
        "_-."
    )

    invalid_characters = [
        character
        for character in normalized
        if character not in allowed_characters
    ]

    if invalid_characters:
        raise ValueError(
            "用户名只能包含英文字母、数字、"
            "下划线、短横线和英文句点。"
        )

    return normalized


def validate_role(
    role: str,
) -> str:
    """检查角色是否合法。"""

    normalized_role = role.strip().lower()

    if normalized_role not in VALID_ROLES:
        raise ValueError(
            "角色必须是 viewer、editor 或 admin。"
        )

    return normalized_role

def username_exists(
    username: str,
) -> bool:
    """
    检查用户名是否已经存在。

    用户名会先进行小写转换和格式校验。
    """

    normalized_username = (
        validate_username(
            username
        )
    )

    with session_scope() as session:
        user_id = session.scalar(
            select(User.id).where(
                User.username
                == normalized_username
            )
        )

        return user_id is not None

def create_user(
    username: str,
    password: str,
    role: str = "viewer",
) -> AuthenticatedUser:
    """创建新用户。"""

    normalized_username = validate_username(
        username
    )

    normalized_role = validate_role(
        role
    )

    password_hash = hash_password(
        password
    )

    with session_scope() as session:
        existing_user = session.scalar(
            select(User).where(
                User.username
                == normalized_username
            )
        )

        if existing_user is not None:
            raise ValueError(
                f"用户名 {normalized_username!r} 已存在。"
            )

        user = User(
            username=normalized_username,
            password_hash=password_hash,
            role=normalized_role,
            is_active=True,
        )

        session.add(user)

        # 立即写入数据库并生成user.id
        session.flush()

        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
        )


def authenticate_user(
    username: str,
    password: str,
) -> AuthenticatedUser | None:
    """
    验证用户名和密码。

    验证成功：
        返回AuthenticatedUser

    验证失败：
        返回None
    """

    normalized_username = normalize_username(
        username
    )

    if not normalized_username:
        return None

    if not password:
        return None

    with session_scope() as session:
        user = session.scalar(
            select(User).where(
                User.username
                == normalized_username
            )
        )

        if user is None:
            return None

        if not user.is_active:
            return None

        password_correct = verify_password(
            password,
            user.password_hash,
        )

        if not password_correct:
            return None

        # 如果Argon2参数升级，
        # 登录成功后自动重新生成密码哈希
        if password_needs_rehash(
            user.password_hash
        ):
            user.password_hash = hash_password(
                password
            )

        user.last_login_at = utc_now()

        session.flush()

        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
        )


def get_user_by_id(
    user_id: int,
) -> AuthenticatedUser | None:
    """根据用户ID读取用户。"""

    with session_scope() as session:
        user = session.get(
            User,
            user_id,
        )

        if user is None:
            return None

        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
        )


def change_password(
    user_id: int,
    new_password: str,
) -> None:
    """修改用户密码。"""

    new_password_hash = hash_password(
        new_password
    )

    with session_scope() as session:
        user = session.get(
            User,
            user_id,
        )

        if user is None:
            raise ValueError(
                "用户不存在。"
            )

        user.password_hash = (
            new_password_hash
        )


def change_user_role(
    user_id: int,
    new_role: str,
) -> None:
    """修改用户角色。"""

    normalized_role = validate_role(
        new_role
    )

    with session_scope() as session:
        user = session.get(
            User,
            user_id,
        )

        if user is None:
            raise ValueError(
                "用户不存在。"
            )

        user.role = normalized_role


def set_user_active(
    user_id: int,
    is_active: bool,
) -> None:
    """启用或停用用户。"""

    with session_scope() as session:
        user = session.get(
            User,
            user_id,
        )

        if user is None:
            raise ValueError(
                "用户不存在。"
            )

        user.is_active = bool(
            is_active
        )


def user_has_role(
    user: AuthenticatedUser | None,
    *allowed_roles: str,
) -> bool:
    """
    判断用户是否拥有指定角色。

    示例：
        user_has_role(user, "editor", "admin")
    """

    if user is None:
        return False

    if not user.is_active:
        return False

    normalized_roles = {
        role.strip().lower()
        for role in allowed_roles
    }

    return user.role in normalized_roles


def require_role(
    user: AuthenticatedUser | None,
    *allowed_roles: str,
) -> None:
    """
    检查操作权限。

    无权限时直接抛出PermissionError。
    """

    if user is None:
        raise PermissionError(
            "请先登录。"
        )

    if not user.is_active:
        raise PermissionError(
            "当前账号已经停用。"
        )

    if not user_has_role(
        user,
        *allowed_roles,
    ):
        raise PermissionError(
            "当前账号没有执行该操作的权限。"
        )
    
def admin_exists() -> bool:
    """
    判断系统中是否已经存在管理员账号。
    """

    with session_scope() as session:
        admin_id = session.scalar(
            select(User.id)
            .where(
                User.role == "admin",
                User.is_active.is_(True),
            )
            .limit(1)
        )

        return admin_id is not None