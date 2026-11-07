from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.commands.assign_task import AssignTaskHandler
from app.application.commands.authenticate import AuthenticateHandler
from app.application.commands.create_status import CreateStatusHandler
from app.application.commands.create_task import CreateTaskHandler
from app.application.commands.delete_status import DeleteStatusHandler
from app.application.commands.delete_task import DeleteTaskHandler
from app.application.commands.logout import LogoutHandler
from app.application.commands.move_task import MoveTaskHandler
from app.application.commands.refresh_tokens import RefreshTokensHandler
from app.application.commands.register_user import RegisterUserHandler
from app.application.commands.rename_status import RenameStatusHandler
from app.application.commands.reorder_status import ReorderStatusHandler
from app.application.commands.update_task import UpdateTaskHandler
from app.application.ports.clock import Clock
from app.application.ports.health import HealthProbe
from app.application.ports.notifier import Notifier
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.refresh_token_store import RefreshTokenStore
from app.application.ports.token_service import TokenService
from app.application.ports.unit_of_work import UnitOfWork
from app.application.queries.board import GetBoardHandler
from app.application.queries.get_status import GetStatusHandler
from app.application.queries.get_user import GetUserByIdHandler
from app.application.queries.list_statuses import ListStatusesHandler
from app.application.queries.list_users import ListUsersHandler
from app.application.queries.tasks import GetTaskHandler, ListTasksHandler
from app.infrastructure.clock import utc_now
from app.infrastructure.config import Settings
from app.infrastructure.health import ServiceHealthProbe
from app.infrastructure.queries.board import SqlAlchemyGetBoardHandler
from app.infrastructure.queries.statuses import (
    SqlAlchemyGetStatusHandler,
    SqlAlchemyListStatusesHandler,
)
from app.infrastructure.queries.tasks import SqlAlchemyGetTaskHandler, SqlAlchemyListTasksHandler
from app.infrastructure.queries.users import (
    SqlAlchemyGetUserByIdHandler,
    SqlAlchemyListUsersHandler,
)
from app.infrastructure.security.jwt_token_service import JwtTokenService
from app.infrastructure.security.redis_refresh_token_store import RedisRefreshTokenStore
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


# --- services -------------------------------------------------------------------


def get_clock() -> Clock:
    return utc_now


def get_password_hasher(request: Request) -> PasswordHasher:
    # Built once in create_app: constructing it computes a bcrypt dummy hash.
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


def get_token_service(
    settings: SettingsDep, clock: Annotated[Clock, Depends(get_clock)]
) -> TokenService:
    return JwtTokenService(
        secret=settings.jwt_secret.get_secret_value(),
        access_ttl=settings.access_token_ttl,
        refresh_ttl=timedelta(days=settings.refresh_token_expire_days),
        clock=clock,
    )


def get_refresh_token_store(redis: RedisDep) -> RefreshTokenStore:
    return RedisRefreshTokenStore(redis)


def get_health_probe(session: SessionDep, redis: RedisDep, settings: SettingsDep) -> HealthProbe:
    return ServiceHealthProbe(session, redis, timeout=settings.health_check_timeout_seconds)


def get_notifier(request: Request) -> Notifier:
    notifier: Notifier = request.app.state.notifier
    return notifier


def get_unit_of_work(session: SessionDep) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


ClockDep = Annotated[Clock, Depends(get_clock)]
PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
RefreshTokenStoreDep = Annotated[RefreshTokenStore, Depends(get_refresh_token_store)]
UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]
NotifierDep = Annotated[Notifier, Depends(get_notifier)]


# --- command handlers -----------------------------------------------------------


def get_register_user_handler(
    uow: UnitOfWorkDep, hasher: PasswordHasherDep, clock: ClockDep
) -> RegisterUserHandler:
    return RegisterUserHandler(uow=uow, hasher=hasher, clock=clock)


def get_authenticate_handler(
    uow: UnitOfWorkDep, hasher: PasswordHasherDep, tokens: TokenServiceDep
) -> AuthenticateHandler:
    return AuthenticateHandler(uow=uow, hasher=hasher, tokens=tokens)


def get_refresh_tokens_handler(
    uow: UnitOfWorkDep, tokens: TokenServiceDep, store: RefreshTokenStoreDep, clock: ClockDep
) -> RefreshTokensHandler:
    return RefreshTokensHandler(uow=uow, tokens=tokens, store=store, clock=clock)


def get_logout_handler(tokens: TokenServiceDep, store: RefreshTokenStoreDep) -> LogoutHandler:
    return LogoutHandler(tokens=tokens, store=store)


def get_create_status_handler(uow: UnitOfWorkDep, clock: ClockDep) -> CreateStatusHandler:
    return CreateStatusHandler(uow=uow, clock=clock)


def get_rename_status_handler(uow: UnitOfWorkDep) -> RenameStatusHandler:
    return RenameStatusHandler(uow=uow)


def get_reorder_status_handler(uow: UnitOfWorkDep) -> ReorderStatusHandler:
    return ReorderStatusHandler(uow=uow)


def get_delete_status_handler(uow: UnitOfWorkDep) -> DeleteStatusHandler:
    return DeleteStatusHandler(uow=uow)


def get_create_task_handler(
    uow: UnitOfWorkDep, clock: ClockDep, notifier: NotifierDep
) -> CreateTaskHandler:
    return CreateTaskHandler(uow=uow, clock=clock, notifier=notifier)


def get_update_task_handler(uow: UnitOfWorkDep, clock: ClockDep) -> UpdateTaskHandler:
    return UpdateTaskHandler(uow=uow, clock=clock)


def get_delete_task_handler(uow: UnitOfWorkDep) -> DeleteTaskHandler:
    return DeleteTaskHandler(uow=uow)


def get_move_task_handler(uow: UnitOfWorkDep, clock: ClockDep) -> MoveTaskHandler:
    return MoveTaskHandler(uow=uow, clock=clock)


def get_assign_task_handler(
    uow: UnitOfWorkDep, clock: ClockDep, notifier: NotifierDep
) -> AssignTaskHandler:
    return AssignTaskHandler(uow=uow, clock=clock, notifier=notifier)


# --- query handlers -------------------------------------------------------------


def get_user_by_id_handler(session: SessionDep) -> GetUserByIdHandler:
    return SqlAlchemyGetUserByIdHandler(session)


def get_list_users_handler(session: SessionDep) -> ListUsersHandler:
    return SqlAlchemyListUsersHandler(session)


def get_status_handler(session: SessionDep) -> GetStatusHandler:
    return SqlAlchemyGetStatusHandler(session)


def get_list_statuses_handler(session: SessionDep) -> ListStatusesHandler:
    return SqlAlchemyListStatusesHandler(session)


def get_task_handler(session: SessionDep) -> GetTaskHandler:
    return SqlAlchemyGetTaskHandler(session)


def get_list_tasks_handler(session: SessionDep) -> ListTasksHandler:
    return SqlAlchemyListTasksHandler(session)


def get_board_handler(session: SessionDep) -> GetBoardHandler:
    return SqlAlchemyGetBoardHandler(session)
