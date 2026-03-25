from typing import AsyncGenerator, Callable, Any, Optional

import asyncpg
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
import logging

from app.core.config import settings
from app.core.security import SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)

DATABASE_URL: str = settings.database_url

db_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> None:
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
        logger.info("Conexion con PostgreSQL V2 exitosa y conectada!")
    except Exception as e:
        logger.error(f"Error al conectar al Pool PQRS V2: {e}")
        raise


def get_raw_pool() -> Optional[asyncpg.Pool]:
    return db_pool


async def close_db_pool() -> None:
    if db_pool:
        await db_pool.close()
        logger.info("Pool PostgreSQL cerrado correctamente")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

RLS_VARS = ("app.current_tenant_id", "app.current_user_id", "app.current_role", "app.is_superuser")


async def get_db_connection(
    token: Optional[str] = Depends(oauth2_scheme),
) -> AsyncGenerator[asyncpg.Connection, None]:
    if db_pool is None:
        raise HTTPException(status_code=500, detail="Database Pool no inicializado")

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    role: str = "analista"

    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            tenant_id = payload.get("tenant_uuid")
            user_id = payload.get("usuario_id")
            role = payload.get("role", "analista")
        except Exception:
            raise HTTPException(status_code=401, detail="Token invalido o expirado")

    async with db_pool.acquire() as connection:
        if tenant_id:
            await connection.execute(
                "SELECT set_config('app.current_tenant_id', $1, false)", tenant_id
            )
            if user_id:
                await connection.execute(
                    "SELECT set_config('app.current_user_id', $1, false)", user_id
                )
            await connection.execute(
                "SELECT set_config('app.current_role', $1, false)", role
            )
            if role == "super_admin":
                await connection.execute(
                    "SELECT set_config('app.is_superuser', 'true', false)"
                )

        try:
            yield connection
        finally:
            if tenant_id:
                for var in RLS_VARS:
                    await connection.execute(f"RESET {var}")


async def execute_in_rls_context(
    conn: asyncpg.Connection,
    tenant_id: str,
    role: str,
    action: Callable[[asyncpg.Connection], Any],
    user_id: Optional[str] = None,
) -> Any:
    try:
        await conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, false)", tenant_id
        )
        if user_id:
            await conn.execute(
                "SELECT set_config('app.current_user_id', $1, false)", user_id
            )
        await conn.execute(
            "SELECT set_config('app.current_role', $1, false)", role
        )
        return await action(conn)
    finally:
        for var in RLS_VARS:
            await conn.execute(f"RESET {var}")
