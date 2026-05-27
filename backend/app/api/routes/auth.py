from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.db import get_db_connection
from app.core.security import verify_password, create_access_token, get_password_hash, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
import uuid

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Schema Entrada de Pydantic
class TokenRequest(BaseModel):
    email: str
    password: str

# Schema Salida
class Token(BaseModel):
    access_token: str
    token_type: str
    user: Optional[Dict[str, Any]] = None

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, form_data: TokenRequest, conn = Depends(get_db_connection)):
    """
    1. Verifica usuario por Email
    2. Compara el Hash de Password (bcrypt)
    3. Retorna un JWT con el Token Claims (Roles y Tenant RLS)
    """
    # 1. Buscar Usuario (Case Insensitive) + Nombre de Cliente
    query = """
    SELECT u.id, u.cliente_id, u.nombre, u.password_hash, u.rol, u.debe_cambiar_password, c.nombre as cliente_nombre
    FROM usuarios u
    JOIN clientes_tenant c ON u.cliente_id = c.id
    WHERE LOWER(u.email) = LOWER($1)
    """
    # Bypass RLS solo durante el SELECT de login (anonymous, sin tenant context aún).
    # Hay que setear AMBOS GUCs porque la policy evalúa ambos lados del OR sin
    # short-circuit, y `current_setting('app.current_tenant_id', true)::uuid`
    # falla con InvalidTextRepresentation si está vacío. SET LOCAL vive 1 tx.
    async with conn.transaction():
        await conn.execute("SET LOCAL app.current_tenant_id = '00000000-0000-0000-0000-000000000000'")
        await conn.execute("SET LOCAL app.is_superuser = 'true'")
        usuario = await conn.fetchrow(query, form_data.email)

    # 2. Verificar Existencia y Contraseña
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Hash Validation
    if not verify_password(form_data.password, usuario["password_hash"]):
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
         )

    # 4. JWT Configuración
    access_token = create_access_token(
        data={
            "sub": form_data.email, 
            "tenant_uuid": str(usuario["cliente_id"]),
            "role": usuario["rol"],
            "usuario_id": str(usuario["id"]),
            "nombre": usuario["nombre"]
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "id": str(usuario["id"]),
            "email": form_data.email,
            "nombre": usuario["nombre"],
            "rol": usuario["rol"],
            "tenant_uuid": str(usuario["cliente_id"]),
            "cliente_nombre": usuario["cliente_nombre"],
            "debe_cambiar_password": usuario["debe_cambiar_password"]
        }
    }

class ChangePasswordRequest(BaseModel):
    new_password: str

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: Any = Depends(get_current_user),
    conn = Depends(get_db_connection)
):
    """
    Ruta para que el usuario cambie su contraseña obligatoriamente.
    """
    new_hash = get_password_hash(data.new_password)

    query = "UPDATE usuarios SET password_hash = $1, debe_cambiar_password = FALSE WHERE id = $2"
    await conn.execute(query, new_hash, uuid.UUID(current_user.usuario_id))

    return {"status": "success", "message": "Contraseña actualizada correctamente"}


@router.get("/me")
async def me(
    current_user: Any = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    """Info del usuario autenticado + tenant + workflows disponibles.

    Sprint FlexFintech 2026-05-27 — bloque 7. El frontend lo usa al boot para
    decidir si mostrar el filtro PQRS|AC en Bandeja y la sección AC en
    Dashboard (solo para tenants que tienen buzones con ATENCION_CLIENTE).

    `workflows_disponibles` se calcula como DISTINCT tipo_workflow de los
    config_buzones is_active=TRUE del tenant. Para super_admin (sin tenant
    propio) devuelve el set global ["PQRS", "ATENCION_CLIENTE"] si hay buzones
    AC en cualquier tenant, sino solo ["PQRS"]. Default seguro: ["PQRS"].
    """
    es_super = current_user.role == 'super_admin'

    if es_super:
        rows = await conn.fetch(
            "SELECT DISTINCT tipo_workflow FROM config_buzones WHERE is_active = TRUE"
        )
        tenant_info = None
    else:
        rows = await conn.fetch(
            "SELECT DISTINCT tipo_workflow FROM config_buzones "
            "WHERE cliente_id = $1::uuid AND is_active = TRUE",
            uuid.UUID(current_user.tenant_uuid),
        )
        t = await conn.fetchrow(
            "SELECT id, nombre FROM clientes_tenant WHERE id = $1::uuid",
            uuid.UUID(current_user.tenant_uuid),
        )
        tenant_info = {"id": str(t["id"]), "nombre": t["nombre"]} if t else None

    workflows = sorted({r["tipo_workflow"] for r in rows}) or ["PQRS"]

    return {
        "usuario_id": current_user.usuario_id,
        "email": current_user.email,
        "nombre": current_user.nombre,
        "rol": current_user.role,
        "tenant": tenant_info,
        "workflows_disponibles": workflows,
    }
