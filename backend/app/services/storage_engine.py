import os
import logging
import time
from minio import Minio
from datetime import timedelta

logger = logging.getLogger(__name__)

MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "adminminio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "adminpassword")
BUCKET_NAME = "pqrs-vault"

def _parse_endpoint(raw: str) -> tuple[str, bool]:
    """
    Normaliza el endpoint de MinIO: elimina prefijos de protocolo
    y determina si usar SSL basado en https://.
    Retorna (host:port, secure).
    """
    raw = raw.strip()
    if raw.startswith("https://"):
        return raw.removeprefix("https://").rstrip("/"), True
    if raw.startswith("http://"):
        return raw.removeprefix("http://").rstrip("/"), False
    return raw, False


_raw_endpoint = os.getenv("MINIO_ENDPOINT", "miniov2:9000")
MINIO_ENDPOINT, _use_ssl = _parse_endpoint(_raw_endpoint)

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=_use_ssl,
)


def ensure_bucket(retries: int = 3, delay: float = 2.0):
    """Asegura que el bucket de la boveda existe, con reintentos."""
    for attempt in range(1, retries + 1):
        try:
            if not client.bucket_exists(BUCKET_NAME):
                client.make_bucket(BUCKET_NAME)
                logger.info(f"Bucket '{BUCKET_NAME}' creado exitosamente.")
            return
        except Exception as e:
            logger.warning(
                f"MinIO intento {attempt}/{retries} fallo: {e}"
            )
            if attempt < retries:
                time.sleep(delay)
    logger.error(
        f"No se pudo conectar con MinIO en '{MINIO_ENDPOINT}' tras {retries} intentos. "
        "El almacenamiento de archivos no estara disponible hasta que MinIO responda."
    )


async def upload_file(file_data, file_name, folder="general"):
    """
    Sube un archivo a la Boveda MinIO.
    Retorna la ruta del objeto (object_name).
    """
    try:
        object_name = f"{folder}/{file_name}"
        from io import BytesIO
        stream = BytesIO(file_data)

        client.put_object(
            BUCKET_NAME,
            object_name,
            stream,
            length=len(file_data),
        )
        return object_name
    except Exception as e:
        logger.error(f"Error al subir archivo a MinIO: {e}")
        return None


MINIO_PUBLIC_URL = os.getenv("MINIO_PUBLIC_URL", "")


def get_download_url(object_name):
    """Genera una URL temporal para descarga (Presigned URL)."""
    try:
        url = client.get_presigned_url(
            "GET",
            BUCKET_NAME,
            object_name,
            expires=timedelta(hours=2),
        )
        if MINIO_PUBLIC_URL and url:
            url = url.replace(f"http://{MINIO_ENDPOINT}", MINIO_PUBLIC_URL, 1)
        return url
    except Exception as e:
        logger.error(f"Error al generar URL de descarga: {e}")
        return None


def download_file(object_name: str) -> bytes | None:
    """Descarga un archivo de MinIO y retorna los bytes."""
    try:
        response = client.get_object(BUCKET_NAME, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except Exception as e:
        logger.error(f"Error al descargar {object_name} desde MinIO: {e}")
        return None


ensure_bucket()
