import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)

SECRET_KEY = settings.jwt_secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v2/auth/login")

class UserInToken(BaseModel):
    email: str
    tenant_uuid: str
    role: str
    nombre: Optional[str] = None
    usuario_id: Optional[str] = None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si el hash bcrypt en DB coincide con la contraseña plana"""
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)

def get_password_hash(password: str) -> str:
    """Genera hash de la contraseña usando bcrypt (El estándar PQR V2)"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea token JWT que incluye el `cliente_id` u `organización_id` en el Payload para RLS"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token inválido: {e}")
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInToken:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tokens inviable o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserInToken(
        email=payload.get("sub"),
        tenant_uuid=payload.get("tenant_uuid"),
        role=payload.get("role"),
        nombre=payload.get("nombre"),
        usuario_id=payload.get("usuario_id")
    )
