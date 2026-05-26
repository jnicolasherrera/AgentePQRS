# RUNBOOK — RLS defensa en profundidad (rol del backend sin BYPASSRLS)

**Objetivo:** que las policies RLS de Postgres sean la **segunda barrera real**
del aislamiento multi-tenant (la primera es el filtro explícito `cliente_id`
agregado en PR #8 / SEC-2026-05-21).

**Estado actual (2026-05-26):**
- ✅ **Staging**: aplicado y validado.
- ⏸️ **Prod**: pendiente — replicar este runbook en una ventana corta.

## Por qué hace falta

El backend conecta con `pqrs_admin`, que es **SUPERUSER + BYPASSRLS + OWNER**
de las tablas tenant-scoped. Cualquiera de las tres condiciones hace que las
policies RLS no se apliquen. Hoy el aislamiento depende exclusivamente del
filtro explícito en el código.

## Cambios

1. **Rol nuevo** `pqrs_backend`: `NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB`.
2. **Grants explícitos** (ALL en todas las tablas del schema public + default privileges).
3. **FORCE RLS** activado en `pqrs_adjuntos` y `pqrs_comentarios` (las únicas
   sin FORCE; `pqrs_casos` y `usuarios` ya lo tenían). Sin FORCE, el owner
   pasa por las policies aunque sean activadas.
4. **`DATABASE_URL` del backend** apunta al nuevo rol. Workers siguen con
   `pqrs_admin` (procesan multi-tenant, no se aíslan por contexto).

## Procedimiento (ejecutado en staging, replicable en prod)

### 1. Generar password random + crear rol + grants + FORCE RLS

```bash
NEWPASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
SQL="
CREATE ROLE pqrs_backend WITH LOGIN PASSWORD '$NEWPASS' NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
GRANT USAGE ON SCHEMA public TO pqrs_backend;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public TO pqrs_backend;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO pqrs_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pqrs_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO pqrs_backend;
ALTER TABLE pqrs_adjuntos FORCE ROW LEVEL SECURITY;
ALTER TABLE pqrs_comentarios FORCE ROW LEVEL SECURITY;
"
echo "$SQL" | ssh ubuntu@<HOST> 'docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2'
echo "$NEWPASS" > /tmp/pqrs_backend_pass && chmod 600 /tmp/pqrs_backend_pass
```

### 2. Actualizar `DATABASE_URL` del backend en `docker-compose.yml`

**Cambio quirúrgico**: solo la línea del servicio `backend_v2`
(probablemente línea ~81, verificar con `grep -n DATABASE_URL docker-compose.yml`).
**NO tocar** las de `master_worker_v2` y `demo_worker_v2`.

```bash
TS=$(date +%Y%m%d_%H%M%S)
ssh ubuntu@<HOST> "cp /home/ubuntu/PQRS_V2/docker-compose.yml /home/ubuntu/PQRS_V2/docker-compose.yml.bak-$TS"
cat /tmp/pqrs_backend_pass | ssh ubuntu@<HOST> 'read P && sed -i "81s|.*|      - DATABASE_URL=postgresql://pqrs_backend:${P}@postgres_v2:5432/pqrs_v2|" /home/ubuntu/PQRS_V2/docker-compose.yml'
```

### 3. Recreate solo el backend (workers intactos)

```bash
ssh ubuntu@<HOST> 'cd /home/ubuntu/PQRS_V2 && docker compose up -d backend_v2'
```

### 4. Validación

- Backend `Up` y sin errores en logs (`docker logs --tail 20 pqrs_v2_backend`).
- HTTP `https://<host>/` → 200 (frontend OK).
- Suite pytest: `docker compose run --rm --no-deps backend_v2 python -m pytest tests/ -q` → 88 passed (idéntico al baseline).
- **Probe RLS con el rol nuevo** (clave):
  ```bash
  PASS=$(cat /tmp/pqrs_backend_pass)
  ssh ubuntu@<HOST> "docker exec -e PGPASSWORD='$PASS' pqrs_v2_db psql -U pqrs_backend -d pqrs_v2 -c \"
    SELECT set_config('app.current_tenant_id', '<UUID-de-un-tenant>', false);
    SELECT set_config('app.is_superuser', 'false', false);
    SELECT count(*) AS visibles FROM pqrs_casos;\""
  ```
  Debe devolver solo los casos de ese tenant (no todos).

### 5. Cleanup local
```bash
shred -u /tmp/pqrs_backend_pass
```

## Rollback (si algo falla)

```bash
# revertir docker-compose.yml
ssh ubuntu@<HOST> 'cp /home/ubuntu/PQRS_V2/docker-compose.yml.bak-<TS> /home/ubuntu/PQRS_V2/docker-compose.yml && cd /home/ubuntu/PQRS_V2 && docker compose up -d backend_v2'
# (opcional) borrar el rol — la DB queda sin cambios funcionales
ssh ubuntu@<HOST> 'docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -c "DROP OWNED BY pqrs_backend; DROP ROLE pqrs_backend;"'
# FORCE RLS: los toggles en pqrs_adjuntos/pqrs_comentarios NO rompen nada con pqrs_admin (que es owner y superuser) — se pueden dejar o revertir con NO FORCE ROW LEVEL SECURITY.
```

## Resultado staging (2026-05-26)

- Rol `pqrs_backend` activo, super=false, bypassrls=false.
- FORCE RLS en las 4 tablas.
- Backend funcionando, suite 88 verde, sin errores en logs.
- Probe RLS: con `is_super=false` ve solo los del tenant; con `is_super=true` ve todos.
- **Aislamiento doble**: filtro explícito (PR #8) + policies RLS efectivas.
