import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.db import init_db_pool, close_db_pool
from app.core.config import settings
from app.services.kafka_producer import init_kafka_producer, close_kafka_producer
from app.api.routes import auth, stream, stats, casos, ai, admin, webhooks

logger = logging.getLogger("MAIN")
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    try:
        await init_kafka_producer(settings.kafka_bootstrap_servers)
    except Exception as e:
        logger.warning(f"Kafka no disponible — API arranca sin producer: {e}")
    yield
    await close_kafka_producer()
    await close_db_pool()

app = FastAPI(
    title="FlexPQR API",
    description="API de gestión de PQRS y Tutelas. JWT, RLS Multi-Tenant.",
    version="2.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Integración CORS de React/Next (3003 es el NextJS nuevo)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002", "http://localhost:3003", "http://54.233.39.211:3002", "https://app.flexpqr.com", "https://flexpqr.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cargar los "Enchufes" (Routers)
app.include_router(auth.router, prefix="/api/v2/auth", tags=["Autenticación"])
app.include_router(stream.router, prefix="/api/v2/stream", tags=["SSE Streaming Redis"])
app.include_router(stats.router, prefix="/api/v2/stats", tags=["Dashboard Estadísticas"])
app.include_router(casos.router, prefix="/api/v2/casos", tags=["Detalles Casos Triaje"])
app.include_router(ai.router, prefix="/api/v2/ai", tags=["Inteligencia Artificial"])
app.include_router(admin.router, prefix="/api/v2/admin", tags=["Administración"])
# Webhooks sin prefijo /v2/ — Microsoft/Google no pasan por auth JWT
app.include_router(webhooks.router, prefix="/api")


@app.get("/")
def home_check():
    return {"status": "ok", "message": "FlexPQR API está VIVO."}
