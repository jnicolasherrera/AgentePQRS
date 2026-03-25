from enum import Enum

class TipoCaso(str, Enum):
    TUTELA = "TUTELA"
    PETICION = "PETICION"
    QUEJA = "QUEJA"
    RECLAMO = "RECLAMO"
    SOLICITUD = "SOLICITUD"
    CONSULTA = "CONSULTA"
    FELICITACION = "FELICITACION"

class EstadoCaso(str, Enum):
    NUEVO = "NUEVO"
    EN_PROCESO = "EN_PROCESO"
    PENDIENTE_INFO = "PENDIENTE_INFO"
    RESPONDIDO = "RESPONDIDO"
    CERRADO = "CERRADO"
    VENCIDO = "VENCIDO"

class Prioridad(str, Enum):
    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"
