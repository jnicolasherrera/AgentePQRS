"""
SQLAlchemy 2.0 ORM models para Aequitas.
Fuente de verdad: migraciones SQL en aequitas_infrastructure/database/
Estos modelos reflejan el esquema real - NO son la fuente de verdad para DDL.
Alembic se usara solo para evolucion futura de tablas de negocio.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Boolean, Text, BigInteger, Date,
    ForeignKey, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, INET
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class ClienteTenant(Base):
    __tablename__ = "clientes_tenant"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(255))
    dominio: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(50), default="analista")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint(
            "rol IN ('admin', 'coordinador', 'analista', 'auditor', 'super_admin', 'bot')",
            name="ck_usuarios_rol",
        ),
    )


class PqrsCaso(Base):
    __tablename__ = "pqrs_casos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    email_origen: Mapped[Optional[str]] = mapped_column(String(255))
    asunto: Mapped[Optional[str]] = mapped_column(Text)
    cuerpo: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(50), default="ABIERTO")
    nivel_prioridad: Mapped[str] = mapped_column(String(50), default="NORMAL")
    fecha_recibido: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    tipo_caso: Mapped[Optional[str]] = mapped_column(String(50))
    fecha_vencimiento: Mapped[Optional[datetime]] = mapped_column()
    borrador_respuesta: Mapped[Optional[str]] = mapped_column(Text)
    borrador_estado: Mapped[str] = mapped_column(String(20), default="SIN_PLANTILLA")
    problematica_detectada: Mapped[Optional[str]] = mapped_column(String(100))
    plantilla_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plantillas_respuesta.id", ondelete="SET NULL"),
    )
    aprobado_por: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    aprobado_at: Mapped[Optional[datetime]] = mapped_column()
    enviado_at: Mapped[Optional[datetime]] = mapped_column()
    alerta_2h_enviada: Mapped[bool] = mapped_column(Boolean, default=False)
    acuse_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    numero_radicado: Mapped[Optional[str]] = mapped_column(String(30))
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4
    )
    asignado_a: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    semaforo_sla: Mapped[str] = mapped_column(String(10), default="VERDE")

    __table_args__ = (
        CheckConstraint(
            "semaforo_sla IN ('VERDE', 'AMARILLO', 'ROJO')",
            name="ck_pqrs_casos_semaforo_sla",
        ),
    )


class PqrsAdjunto(Base):
    __tablename__ = "pqrs_adjuntos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    caso_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pqrs_casos.id", ondelete="CASCADE")
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    tamano_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    es_reply: Mapped[bool] = mapped_column(Boolean, default=False)


class PqrsComentario(Base):
    __tablename__ = "pqrs_comentarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    caso_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pqrs_casos.id", ondelete="CASCADE")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE")
    )
    comentario: Mapped[str] = mapped_column(Text)
    tipo_evento: Mapped[str] = mapped_column(String(50), default="COMENTARIO")
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )


class ConfigBuzon(Base):
    __tablename__ = "config_buzones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    email_buzon: Mapped[str] = mapped_column(String(255))
    azure_folder_id: Mapped[Optional[str]] = mapped_column(String(255))
    azure_client_id: Mapped[Optional[str]] = mapped_column(String(255))
    azure_client_secret: Mapped[Optional[str]] = mapped_column(Text)
    azure_tenant_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    proveedor: Mapped[str] = mapped_column(String(50), default="OUTLOOK")
    zoho_refresh_token: Mapped[Optional[str]] = mapped_column(Text)
    zoho_account_id: Mapped[Optional[str]] = mapped_column(String(255))


class PlantillaRespuesta(Base):
    __tablename__ = "plantillas_respuesta"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    problematica: Mapped[str] = mapped_column(String(100))
    contexto: Mapped[Optional[str]] = mapped_column(Text)
    cuerpo: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )


class AuditLogRespuesta(Base):
    __tablename__ = "audit_log_respuestas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    caso_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pqrs_casos.id", ondelete="CASCADE")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE")
    )
    accion: Mapped[str] = mapped_column(String(30))
    lote_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    ip_origen: Mapped[Optional[str]] = mapped_column(INET)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )


class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tabla_afectada: Mapped[str] = mapped_column(String(50))
    registro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes_tenant.id", ondelete="CASCADE")
    )
    accion: Mapped[str] = mapped_column(String(30))
    delta_antes: Mapped[Optional[dict]] = mapped_column(JSONB)
    delta_despues: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_origen: Mapped[Optional[str]] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "accion IN ('INSERT', 'UPDATE', 'DELETE', 'VIEW')",
            name="ck_logs_auditoria_accion",
        ),
    )


class FestivosColombia(Base):
    __tablename__ = "festivos_colombia"

    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    descripcion: Mapped[Optional[str]] = mapped_column(String(100))
