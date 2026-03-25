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
