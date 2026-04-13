# Infraestructura y Operaciones — Sesión 8 abril 2026

## 502 Bad Gateway — Causa y fix definitivo

### Causa raíz
Nginx cachea la IP interna del contenedor al arrancar. Cuando Docker
reinicia un contenedor (frontend o backend) le asigna una IP nueva.
Nginx seguía apuntando a la IP vieja → 502.

### Fix inmediato
```bash
docker compose restart nginx_ssl
```
Nginx re-resuelve el DNS interno y recupera la IP correcta.

### Fix permanente aplicado
- **Archivo**: `nginx/nginx.conf`
- **Cambio**: agregado `resolver 127.0.0.11 valid=30s ipv6=off` en cada bloque server con proxy_pass
- **Además**: proxy_pass usa variables `$upstream_backend` y `$upstream_frontend` en lugar de hostnames directos
- **Efecto**: Nginx re-resuelve el DNS cada 30 segundos automáticamente. Nunca más 502 por IP cacheada.

## Procedimiento de deploy frontend — REGLA INMUTABLE

**NUNCA**: `docker compose up --build` para el frontend

**SIEMPRE**:
1. `docker exec pqrs_v2_frontend sh -c 'cd /app && npm run build'`
2. `docker compose restart frontend_v2`

**Razón**: el bind mount `./frontend:/app` sobreescribe el build del Dockerfile.

## Staging 15.229.114.148 — estado y acceso

### Problema encontrado (8 abril 2026)
Staging no tenía certificados SSL (`server.key`, `flexpqr.key`, `app.flexpqr.key`).
Nginx crasheaba en loop → `ERR_CONNECTION_REFUSED` desde browser.

### Fix aplicado
- Generados certificados self-signed con openssl
- Creados symlinks para los 3 pares cert/key requeridos por nginx.conf
- Staging accesible en: https://15.229.114.148 (aceptar warning cert self-signed)

### Acceso SSH staging
```bash
ssh -i ~/.ssh/flexpqr-staging ubuntu@15.229.114.148
```

## Clave SSH producción — recuperación (8 abril 2026)

### Problema
La clave flexpqr-prod se perdió. No estaba en `C:/Users/juann/.ssh/` ni en ningún disco montado en WSL.

### Solución
- Acceso recuperado via **EC2 Instance Connect** (consola AWS, sin clave)
- Nueva clave ED25519 generada en WSL: `~/.ssh/flexpqr-prod`
- Clave pública agregada a `~/.ssh/authorized_keys` en el servidor

### Comandos de conexión actualizados
```bash
# Producción
ssh -i ~/.ssh/flexpqr-prod ubuntu@18.228.54.9

# Staging
ssh -i ~/.ssh/flexpqr-staging ubuntu@15.229.114.148
```

## Eliminación de correos desde bandeja (8 abril 2026)

### Cambios realizados
- Nuevo endpoint `DELETE /admin/casos/lote` para borrar cualquier caso (admin/super_admin)
- Botón "Eliminar correos" en LiveFeed (tab Casos) con select-all y modal confirmación
- Checkboxes habilitados en AdminBandeja para todos los casos (no solo No-PQRS)
- **FK cascade**: se eliminan registros hijos antes del caso principal
  (pqrs_adjuntos, pqrs_comentarios, audit_log_respuestas, pqrs_clasificacion_feedback)

### No acuse en tutelas
- `master_worker_outlook.py`: excluye TUTELA del envío de acuse de recibo
- Condición: `resultado.tipo.value != "TUTELA"`
