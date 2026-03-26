from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2"
    redis_url: str = "redis://redis_v2:6379"
    jwt_secret_key: str = "dev-key-change-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    anthropic_api_key: str = ""
    kafka_bootstrap_servers: str = "kafka_v2:29092"
    microsoft_webhook_secret: str = ""   # Configurar en .env / docker-compose
    google_webhook_token: str = ""       # Configurar en .env / docker-compose

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}


settings = Settings()


# Business Rules: Plazos y Prioridades para PQRS V2
PLAZOS_DIAS_HABILES = {
    "TUTELA": 2,
    "PETICION": 15,
    "QUEJA": 15,
    "RECLAMO": 15,
    "SOLICITUD": 10,
    "CONSULTA": 30,
    "FELICITACION": 5,
}

PRIORIDADES = {
    "TUTELA": "CRITICA",
    "QUEJA": "ALTA",
    "RECLAMO": "ALTA",
    "PETICION": "MEDIA",
    "SOLICITUD": "MEDIA",
    "CONSULTA": "BAJA",
    "FELICITACION": "BAJA",
}
