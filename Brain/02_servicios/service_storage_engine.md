# Service: Storage Engine (MinIO)

## Archivo
`backend/app/services/storage_engine.py`

## Descripcion
Servicio de almacenamiento de archivos usando MinIO (S3-compatible). Maneja upload, download y generacion de URLs temporales para adjuntos de casos PQRS.

## Configuracion

| Variable          | Default          | Descripcion                    |
|-------------------|------------------|--------------------------------|
| MINIO_ENDPOINT    | miniov2:9000     | Endpoint del servidor MinIO    |
| MINIO_ACCESS_KEY  | adminminio       | Access key                     |
| MINIO_SECRET_KEY  | adminpassword    | Secret key                     |
| MINIO_PUBLIC_URL  | (vacio)          | URL publica para presigned URLs|
| BUCKET_NAME       | pqrs-vault       | Nombre del bucket principal    |

## Funciones

### ensure_bucket(retries=3, delay=2.0)
- Se ejecuta al importar el modulo (module-level)
- Crea el bucket `pqrs-vault` si no existe
- 3 reintentos con 2s de delay

### upload_file(file_data, file_name, folder="general")
- Sube bytes a MinIO en `{folder}/{file_name}`
- Retorna el object_name (ruta completa en el bucket)

### get_download_url(object_name)
- Genera presigned URL con 2 horas de expiracion
- Si `MINIO_PUBLIC_URL` esta configurada, reemplaza el endpoint interno por el publico

### download_file(object_name)
- Descarga un archivo de MinIO y retorna los bytes
- Usado por el AI Classifier para Claim Check inverso

## Uso en el Pipeline

### Upload de adjuntos originales (worker)
```
Email con adjuntos -> Worker descarga -> upload_file(bytes, nombre, folder=tenant_id)
```

### Upload de adjuntos de reply (API)
```
POST /casos/{id}/reply-adjuntos -> upload_file(bytes, nombre, folder="reply/{caso_id}")
```

### Claim Check Pattern (Kafka)
```
Kafka producer: adjunto > 1MB -> upload_file() -> solo URI en mensaje
AI Classifier: lee adjunto_s3_uri -> download_file() -> enriquece clasificacion
```

### Descarga de adjuntos (API)
```
GET /casos/{id}/adjuntos/{adj_id}/download -> minio_client.get_object() -> StreamingResponse
```

## Endpoint Parse
`_parse_endpoint()` normaliza el endpoint de MinIO:
- `http://minio:9000` -> `minio:9000`, secure=False
- `https://storage.example.com` -> `storage.example.com`, secure=True
