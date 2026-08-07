"""用户管理业务逻辑。"""

from __future__ import annotations

import json
from dataclasses import (
    asdict,
    dataclass,
)

from sqlalchemy import (
    func,
    select,
    update,
)

from sqlalchemy.exc import (
    IntegrityError,
)

from src.auth.auth_service import (
    AuthenticatedUser,
    normalize_username,
    require_role,
    validate_role,
    validate_username,
)
from src.auth.password import (
    hash_password,
)
from src.db.database import (
    session_scope,
)
from src.db.models import (
    AuditLog,
    ImportBatch,
    SQLRecord,
    User,
)
from src.db.repositories import (
    AuditLogRepository,
)


@dataclass(frozen=True)
class ManagedUserView:
    """提供给用户管理页面的用户信息。"""

    id: int
    username: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None


def _user_to_view(
    user: User,
) -> ManagedUserView:
    return ManagedUserView(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=(
            user.created_at.isoformat()
        ),
        last_login_at=(
            user.last_login_at.isoformat()
            if user.last_login_at
            else None
        ),
    )


def _user_json(
    user: User,
) -> str:
    """
    用户审计信息。

    注意：不能把password_hash写入审计日志。
    """

    return json.dumps(
        asdict(
            _user_to_view(user)
        ),
        ensure_ascii=False,
        sort_keys=True,
    )


class UserManagementService:
    """管理员用户管理服务。"""

    def __init__(self) -> None:
        self.audit_logs = (
            AuditLogRepository()
        )

    @staticmethod
    def _get_user(
        session,
        user_id: int,
    ) -> User:
        user = session.get(
            User,
            user_id,
        )

        if user is None:
            raise ValueError(
                "没有找到对应用户。"
            )

        return user

    @staticmethod
    def _count_active_admins(
        session,
    ) -> int:
        count = session.scalar(
            select(
                func.count(User.id)
            ).where(
                User.role == "admin",
                User.is_active.is_(True),
            )
        )

        return int(count or 0)

    def list_users(
        self,
        current_user: AuthenticatedUser,
    ) -> list[ManagedUserView]:
        require_role(
            current_user,
            "admin",
        )

        with session_scope() as session:
            users = list(
                session.scalars(
                    select(User)
                    .order_by(
                        User.id.asc()
                    )
                ).all()
            )

            return [
                _user_to_view(user)
                for user in users
            ]

    def create_managed_user(
        self,
        *,
        username: str,
        password: str,
        role: str,
        current_user: AuthenticatedUser,
    ) -> ManagedUserView:
        """
        网页创建用户。

        新用户只能先创建为viewer或editor。
        admin角色通过后续角色调整授予。
        """

        require_role(
            current_user,
            "admin",
        )

        normalized_username = (
            validate_username(
                username
            )
        )

        normalized_role = (
            validate_role(
                role
            )
        )

        if normalized_role not in {
            "viewer",
            "editor",
        }:
            raise ValueError(
                "新用户只能创建为 "
                "viewer 或 editor。"
            )

        password_hash = (
            hash_password(
                password
            )
        )

        try:
            with session_scope() as session:
                existing_user = (
                    session.scalar(
                        select(User).where(
                            User.username
                            == normalized_username
                        )
                    )
                )

                if existing_user is not None:
                    raise ValueError(
                        f"用户名 "
                        f"{normalized_username!r} "
                        "已经存在，请更换用户名。"
                    )

                user = User(
                    username=(
                        normalized_username
                    ),
                    password_hash=(
                        password_hash
                    ),
                    role=normalized_role,
                    is_active=True,
                )

                session.add(user)
                session.flush()

                self.audit_logs.create(
                    session,
                    user_id=current_user.id,
                    action="USER_CREATE",
                    record_id=None,
                    old_value=None,
                    new_value=_user_json(user),
                )

                return _user_to_view(user)

        except IntegrityError as exc:
            raise ValueError(
                f"用户名 "
                f"{normalized_username!r} "
                "已经存在，请更换用户名。"
            ) from exc

    def change_role(
        self,
        *,
        target_user_id: int,
        new_role: str,
        current_user: AuthenticatedUser,
    ) -> ManagedUserView:
        require_role(
            current_user,
            "admin",
        )

        normalized_role = (
            validate_role(
                new_role
            )
        )

        with session_scope() as session:
            target_user = self._get_user(
                session,
                target_user_id,
            )

            if (
                target_user.id
                == current_user.id
                and normalized_role
                != "admin"
            ):
                raise ValueError(
                    "不能降低当前登录管理员"
                    "自己的角色。"
                )

            if (
                target_user.role == "admin"
                and normalized_role != "admin"
                and target_user.is_active
                and self._count_active_admins(
                    session
                ) <= 1
            ):
                raise ValueError(
                    "该用户是系统中最后一个"
                    "有效管理员，不能降级。"
                )

            if (
                target_user.role
                == normalized_role
            ):
                raise ValueError(
                    "用户已经是该角色，"
                    "无需重复修改。"
                )

            old_value = _user_json(
                target_user
            )

            target_user.role = (
                normalized_role
            )

            session.flush()

            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="USER_ROLE_CHANGE",
                record_id=None,
                old_value=old_value,
                new_value=_user_json(
                    target_user
                ),
            )

            return _user_to_view(
                target_user
            )

    def reset_password(
        self,
        *,
        target_user_id: int,
        new_password: str,
        current_user: AuthenticatedUser,
    ) -> ManagedUserView:
        require_role(
            current_user,
            "admin",
        )

        new_password_hash = (
            hash_password(
                new_password
            )
        )

        with session_scope() as session:
            target_user = self._get_user(
                session,
                target_user_id,
            )

            target_user.password_hash = (
                new_password_hash
            )

            session.flush()

            # 审计日志中绝对不能记录密码
            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="USER_PASSWORD_RESET",
                record_id=None,
                old_value=None,
                new_value=json.dumps(
                    {
                        "target_user_id": (
                            target_user.id
                        ),
                        "username": (
                            target_user.username
                        ),
                        "password_reset": True,
                    },
                    ensure_ascii=False,
                ),
            )

            return _user_to_view(
                target_user
            )

    def set_active(
        self,
        *,
        target_user_id: int,
        is_active: bool,
        current_user: AuthenticatedUser,
    ) -> ManagedUserView:
        require_role(
            current_user,
            "admin",
        )

        with session_scope() as session:
            target_user = self._get_user(
                session,
                target_user_id,
            )

            new_active_status = bool(
                is_active
            )

            if (
                target_user.id
                == current_user.id
                and not new_active_status
            ):
                raise ValueError(
                    "不能停用当前登录的"
                    "管理员账号。"
                )

            if (
                target_user.role == "admin"
                and target_user.is_active
                and not new_active_status
                and self._count_active_admins(
                    session
                ) <= 1
            ):
                raise ValueError(
                    "该用户是系统中最后一个"
                    "有效管理员，不能停用。"
                )

            if (
                target_user.is_active
                == new_active_status
            ):
                status_text = (
                    "启用"
                    if new_active_status
                    else "停用"
                )

                raise ValueError(
                    f"该用户当前已经是"
                    f"{status_text}状态。"
                )

            old_value = _user_json(
                target_user
            )

            target_user.is_active = (
                new_active_status
            )

            session.flush()

            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action=(
                    "USER_ENABLE"
                    if new_active_status
                    else "USER_DISABLE"
                ),
                record_id=None,
                old_value=old_value,
                new_value=_user_json(
                    target_user
                ),
            )

            return _user_to_view(
                target_user
            )
    
    def delete_user(
        self,
        *,
        target_user_id: int,
        current_user: AuthenticatedUser,
    ) -> ManagedUserView:
        """
        永久删除一个已经停用的用户。

        删除用户前，将该用户关联的业务记录中的
        用户ID设为None，保留SQL、导入记录和审计内容。
        """

        require_role(
            current_user,
            "admin",
        )

        with session_scope() as session:
            target_user = self._get_user(
                session,
                target_user_id,
            )

            if (
                target_user.id
                == current_user.id
            ):
                raise ValueError(
                    "不能删除当前登录的管理员账号。"
                )

            if target_user.is_active:
                raise ValueError(
                    "该用户仍处于启用状态。"
                    "请先停用用户，再执行删除。"
                )

            deleted_user_view = (
                _user_to_view(
                    target_user
                )
            )

            old_value = _user_json(
                target_user
            )

            # 先记录删除操作。
            # 日志中的操作用户是当前管理员，
            # 被删除用户信息保存在old_value中。
            self.audit_logs.create(
                session,
                user_id=current_user.id,
                action="USER_DELETE",
                record_id=None,
                old_value=old_value,
                new_value=json.dumps(
                    {
                        "target_user_id": (
                            target_user.id
                        ),
                        "username": (
                            target_user.username
                        ),
                        "deleted": True,
                    },
                    ensure_ascii=False,
                ),
            )

            # 保留该用户创建过的SQL记录，
            # 只清除用户外键关联。
            session.execute(
                update(SQLRecord)
                .where(
                    SQLRecord.created_by
                    == target_user.id
                )
                .values(
                    created_by=None
                )
            )

            session.execute(
                update(SQLRecord)
                .where(
                    SQLRecord.updated_by
                    == target_user.id
                )
                .values(
                    updated_by=None
                )
            )

            # 保留该用户以前产生的审计记录，
            # 但解除外键关联。
            session.execute(
                update(AuditLog)
                .where(
                    AuditLog.user_id
                    == target_user.id
                )
                .values(
                    user_id=None
                )
            )

            # 保留该用户上传的批次信息。
            session.execute(
                update(ImportBatch)
                .where(
                    ImportBatch.uploaded_by
                    == target_user.id
                )
                .values(
                    uploaded_by=None
                )
            )

            session.delete(
                target_user
            )

            session.flush()

            return deleted_user_view