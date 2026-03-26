# Infraestructura: Cold Start Fixes

## Problemas Comunes al Primer Arranque

### 1. Kafka No Arranca
- **Sintoma:** `kafka_v2` se reinicia en loop
- **Causa:** ZooKeeper no esta listo cuando Kafka intenta conectar
- **Fix:** `depends_on: zookeeper_v2` en docker-compose. Si persiste, esperar 30s y `docker compose restart kafka_v2`

### 2. Backend Falla al Conectar a PostgreSQL
- **Sintoma:** `Error al conectar al Pool PQRS V2`
- **Causa:** PostgreSQL aun inicializando
- **Fix:** PostgreSQL tiene health check (`pg_isready`). Si el backend arranco antes, reiniciar: `docker compose restart backend_v2`

### 3. Backend Sin Kafka Producer
- **Sintoma:** Warning `Kafka no disponible -- API arranca sin producer`
- **Impacto:** La API funciona pero no puede publicar a Kafka (webhooks fallan)
- **Fix:** Es un degradado graceful. Reiniciar backend despues de que Kafka este healthy

### 4. MinIO Bucket No Existe
- **Sintoma:** Error al subir adjuntos
- **Causa:** `ensure_bucket()` falla si MinIO no esta listo
- **Fix:** `ensure_bucket()` tiene 3 reintentos con 2s de delay. Si falla, reiniciar backend

### 5. Redis Password Incorrecto
- **Sintoma:** `NOAUTH Authentication required`
- **Causa:** Redis configurado con `--requirepass` pero URL sin password
- **Fix:** Asegurar que REDIS_URL incluya password: `redis://:PASSWORD@redis_v2:6379`

### 6. Tablas No Existen
- **Sintoma:** `relation "pqrs_casos" does not exist`
- **Causa:** Migraciones SQL no se han aplicado
- **Fix:** Aplicar migraciones manualmente:
  ```bash
  docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 < 01_schema_v2.sql
  docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 < 02_rls_security_v2.sql
  # ... etc.
  ```

### 7. Frontend No Conecta al Backend
- **Sintoma:** Network Error en la consola del navegador
- **Causa:** NEXT_PUBLIC_API_URL apunta a produccion, no a localhost
- **Fix:** Rebuild frontend con la URL correcta o acceder via Nginx (puerto 443)
