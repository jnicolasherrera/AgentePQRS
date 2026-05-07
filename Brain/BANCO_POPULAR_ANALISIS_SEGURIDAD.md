# 🏦 Análisis de Exigencias de Seguridad Bancaria — Banco Popular

**Fecha de inicio**: 2026-04-14
**Gatillador**: Mail de Dante Anelli *"Banco Popular: Exigencias de Seguridad Informatica. Pensemos juntos!"*
**Destinatarios del mail**: Nicolas Herrera, Gabriel Cimas, Guillermo Salgado
**En copia**: Martin Pallares, Belen Baldasarre, Micaela Guerra

**Objetivo de este documento**: Preparar insumo técnico para la reunión estratégica del equipo donde se decidirá entre **Camino A** (SaaS multitenant certificado), **Camino B** (deploy dentro del banco), o **Camino C** (híbrido: SaaS + opción on-premise para clientes grandes).

---

## Contexto del mail

Dante reporta que en la reunión comercial con Banco Popular del 13-abril, el principal obstáculo identificado es cumplir con **exigencias de seguridad de nivel bancario**. Pasó el tema por una IA que generó un listado de 13 puntos de requisitos y mencionó 6 deal-breakers comunes.

Dante plantea 2 preguntas:

1. ¿Qué tan cerca estamos de implementar todo esto en AWS y Snowflake?
2. ¿Es posible implementar FlexPQR **DENTRO** de la arquitectura del banco?

**Nota técnica importante**: FlexPQR actualmente **no usa Snowflake**. Stack real: AWS EC2 (sa-east-1) + PostgreSQL 15 + Redis + Kafka + MinIO + Nginx. Pregunta a clarificar con Dante: ¿la mención a Snowflake viene de la IA sin contexto o es un supuesto futuro?

---

## Marco de los 3 caminos posibles

### Camino A — SaaS multitenant certificado (cloud de FlexFintech)

FlexFintech opera la plataforma en AWS, el banco consume como servicio externo. Requiere cumplir los 13 puntos de seguridad. Escalable a múltiples clientes. Inversión alta en certificaciones (SOC 2, ISO 27001, pentest). **Tiempo: 6-12 meses.**

### Camino B — Deploy dentro de la infraestructura del banco

Se instala FlexPQR dentro del perímetro bancario (on-premise o cloud del banco). Los datos nunca salen. Se saltea 60-70% del due diligence. Modelo de negocio cambia: de SaaS a proveedor de software con licencias + implementación + soporte. Riesgo de "robo de herramienta". Alto costo operativo por cliente.

### Camino C — Híbrido

SaaS multitenant para la mayoría + opción on-premise para bancos grandes que exigen perímetro cerrado. Técnicamente factible pero operativamente complejo: dos códigos, dos productos, dos pipelines. Es el modelo típico de Atlassian, GitLab, MongoDB a medida que maduran.

---

## Estructura del análisis

Trabajamos punto por punto del 1 al 13 (orden del mail original). Para cada punto:

1. **Estado actual**: qué tenemos hoy en FlexPQR / FlexFintech
2. **Gap identificado**: qué falta
3. **Esfuerzo estimado**: orden de magnitud (horas / días / semanas / meses / USD)
4. **Notas**: dependencias, riesgos, preguntas abiertas para el equipo

Al final, una sección separada consolida los 6 deal-breakers críticos para revisión rápida, más una recomendación técnica preliminar.

---

## Análisis punto por punto

*(Los puntos se van agregando conforme avanza la sesión con Nico)*

## Punto 1 — Gobierno de seguridad y riesgo

### Estado actual

- ❌ No existe Política Formal de Seguridad de la Información escrita ni firmada
- ❌ No hay CISO ni Responsable de Seguridad de la Información designado (ni formal ni informalmente)
- ❌ No hay matriz de riesgos formal (SARO, ISO 31000, o similar)
- ❌ No hay inventario formal de activos de información
- ❌ No hay proceso formal de gestión de terceros (AWS, Anthropic, GitHub, Zoho, etc.)
- ❌ No hay SGSI (Sistema de Gestión de Seguridad de la Información) documentado

FlexFintech está en el punto de partida típico de una startup temprana en este eje: cero gobierno de seguridad formal. El producto funciona técnicamente, pero no existe capa corporativa de compliance.

### Gap identificado

**Gap completo.** Todos los componentes del Punto 1 están sin hacer:

1. Redactar y firmar Política de Seguridad de la Información
2. Designar formalmente un CISO (puede ser part-time, pero con título formal)
3. Armar matriz de riesgos (SARO simplificado o ISO 31000)
4. Construir inventario de activos con owners asignados
5. Documentar proceso de gestión de terceros / proveedores críticos
6. Armar SGSI básico

### Esfuerzo estimado

**Con consultor externo especializado en compliance bancario colombiano (recomendado)**:

- Costo aproximado: **USD 3.000 a 8.000**
- Tiempo: **4-8 semanas**
- Resultado: paquete completo listo para due diligence

**In-house sin consultor**:

- Costo: solo tiempo de personas
- Tiempo: **2-4 meses** a tiempo parcial
- Riesgo: calidad documental insuficiente para un banco serio

**Recomendación técnica**: consultor externo. Es inversión que sirve para cualquier cliente bancario, de salud, o gobierno — no solo Banco Popular.

### Notas

- Este punto **no requiere cambiar código de FlexPQR**. Es 100% gobierno empresarial y documentación.
- Es pre-requisito absoluto para Camino A (SaaS certificado) y Camino C (híbrido).
- Para Camino B es necesario pero más liviano (el banco asume parte del riesgo en su propia infra).
- **Beneficio lateral**: una vez hecho, sirve también para Bancolombia, otros bancos, aseguradoras, EPS, entidades de gobierno.
- **Preguntas abiertas para el equipo**:
  - ¿Martín/FlexFintech tiene presupuesto para consultor de compliance?
  - ¿Qué consultores conocemos en Colombia o Argentina especializados en banca?
  - ¿Quién va a ser el CISO designado? ¿Un fundador o alguien externo?
- **Responsable principal de cerrar este punto**: Martín (decisión comercial/financiera) con soporte técnico de Nico y Dante.

## Punto 2 — Contrato robusto de tercerización / proveedor crítico

### Estado actual

- ❌ **Contrato con Abogados Recovery (pilot actual)**: acuerdo informal/verbal, no formalizado por escrito
- ❌ **Templates legales B2B**: no existen templates genéricos (NDA, contrato maestro, DPA, SLA). Cada cliente se negocia desde cero
- ❌ **Acuerdo de Procesamiento de Datos (DPA)**: inexistente. Ley 1581/2012 de Colombia lo exige para cualquier tratamiento de datos personales de terceros
- ❌ **Cláusulas de devolución/destrucción de datos al terminar**: no existen
- ❌ **Facultades de auditoría**: no están escritas en ningún lado
- ❌ **SLA formal** (uptime, tiempos de respuesta, penalidades): no existe
- 🟡 **Cifrado en tránsito**: estado técnico real pendiente de verificar. Probablemente HTTPS básico vía Nginx/Cloudflare pero sin certificación de cipher suites específicas ni política documentada

### Gap identificado

**Gap contractual completo.** Los componentes que faltan:

1. Contrato maestro de prestación de servicios B2B (template FlexFintech)
2. NDA estándar (bidireccional, con cláusulas de confidencialidad post-terminación)
3. DPA (Data Processing Agreement) alineado con Ley 1581/2012 y Decreto 1377
4. SLA formal con métricas claras (uptime objetivo, tiempo de respuesta, ventanas de mantenimiento, penalidades)
5. Anexo de seguridad técnica (cifrado, autenticación, backups, retención, destrucción)
6. Cláusulas de auditoría con condiciones razonables (preaviso, frecuencia, costos)
7. Cláusulas de propiedad intelectual (qué es del banco, qué es de FlexFintech)
8. Cláusulas de exit (transición ordenada, devolución de datos en formato usable, plazos)
9. Regularizar contrato con Abogados Recovery usando el mismo paquete

### Esfuerzo estimado

**Con abogado especializado en contratos B2B SaaS (recomendado)**:

- Costo aproximado: **USD 2.000 a 5.000** (paquete completo de templates)
- Tiempo: **3-6 semanas**
- Resultado: paquete legal reutilizable para cualquier cliente B2B
- Beneficio lateral: resuelve también el gap con Recovery y cualquier cliente futuro

**In-house usando templates públicos (no recomendado para banca)**:

- Costo: solo tiempo
- Tiempo: **4-8 semanas**
- Riesgo alto: templates genéricos no cubren exigencias bancarias específicas colombianas. Los abogados del banco los van a rechazar en la primera revisión

**Parte técnica (cifrado en tránsito)**:

- Tiempo de verificación: **30-60 minutos** con el agente Claude Code
- Si hay gaps: **4-8 horas** de trabajo para asegurar TLS 1.2+ en todos los endpoints con cipher suites modernas
- Costo: solo tiempo

### Notas

- Este punto es **contractual y no requiere cambiar el código del producto**. Excepto por la verificación/refuerzo del cifrado en tránsito, que sí es técnico.
- **Deal-breaker si no se resuelve**: sí. Sin contrato robusto, la SFC prohíbe al banco contratarnos, independientemente de qué tan buen producto tengamos.
- Aplica igual a Camino A, B y C. En Camino B es más simple (muchas cláusulas se vuelven triviales porque los datos nunca salen del banco) pero aparece una nueva dimensión: **licencia de software**, que hoy no tenemos formalizada.
- **Preguntas abiertas para el equipo**:
  - ¿Quién en FlexFintech está a cargo del tema legal? ¿Un abogado interno? ¿Alguien externo?
  - ¿Martín conoce abogados especializados en B2B SaaS en Colombia o Argentina?
  - ¿Hay presupuesto para el paquete legal? (USD 2.000-5.000)
  - Prioridad: ¿regularizamos primero Recovery (cliente actual) o armamos templates nuevos en paralelo?
- **Responsable principal de cerrar este punto**: Martín con soporte de abogado externo. Nico + Dante aportan las especificaciones técnicas (cifrado, backups, arquitectura) para que el abogado las formalice.
- **Pendiente técnico para verificar inmediato**: nivel real de cifrado en tránsito actual. Se va a ejecutar como sub-tarea de este punto en el próximo prompt.

---

### Verificación técnica ejecutada (14-abril-2026)

Se ejecutó diagnóstico read-only completo de cifrado en tránsito + exposición de puertos del server EC2 (18.228.54.9). Resultados:

#### Lo que está bien ✅

- **TLS en Nginx público (`app.flexpqr.com:443`)**: solo TLS 1.2 y 1.3 habilitados, rechaza TLS 1.0/1.1 correctamente
- **Certificado SSL**: Let's Encrypt válido hasta 2026-06-17, renovación automática configurada
- **HSTS header**: `max-age=63072000; includeSubDomains` (2 años), aceptable para banca
- **Cipher negociado en runtime**: `ECDHE-ECDSA-AES256-GCM-SHA384` (moderno)
- **Security headers**: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy presentes

#### Observaciones menores 🟡

- `ssl_ciphers HIGH:!aNULL:!MD5` usa filtro genérico, no lista explícita de cipher suites (aceptable pero no ideal)
- Falta `ssl_prefer_server_ciphers on` — el cliente elige el cipher
- Falta `Content-Security-Policy` en headers
- Falta `ssl_stapling` (OCSP stapling)

#### Hallazgos graves 🚨 (DEAL-BREAKER BANCARIO)

**Múltiples servicios internos expuestos directamente a internet sin TLS, saltándose el proxy Nginx**:

| Servicio | Puerto público | Riesgo |
|---|---|---|
| `pqrs_v2_backend` (FastAPI) | `18.228.54.9:8001` | HTTP plano, bypass total del TLS |
| `pqrs_v2_frontend` (Next.js) | `18.228.54.9:3002` | HTTP plano, bypass total del TLS |
| `pqrs_v2_db` (PostgreSQL) | `18.228.54.9:5434` | DB directa a internet |
| `pqrs_v2_redis` | `18.228.54.9:6381` | Cache directo a internet |
| `pqrs_v2_minio` (API) | `18.228.54.9:9020` | Object storage directo |
| `pqrs_v2_minio` (consola) | `18.228.54.9:9021` | Panel admin expuesto |
| `pqrs_staging_backend` | `18.228.54.9:8002` | HTTP plano |
| `pqrs_staging_frontend` | `18.228.54.9:3003` | HTTP plano |
| `pqrs_staging_db` | `18.228.54.9:5435` | DB directa a internet |
| `pqrs_staging_redis` | `18.228.54.9:6382` | Cache directo a internet |
| `evolution_api` (WhatsApp) | `18.228.54.9:8080` | API HTTP expuesta |

Causa raíz: los mapeos de puertos en los `docker-compose.yml` usan formato `"PUERTO_HOST:PUERTO_CONTAINER"` que por default publica en todas las interfaces (`0.0.0.0`). Para aislar a localhost hay que usar `"127.0.0.1:PUERTO_HOST:PUERTO_CONTAINER"`.

#### Impacto en due diligence bancario

**NO PASA**. Un auditor bancario con `nmap 18.228.54.9` descubre los 11 servicios expuestos en 30 segundos. La SFC rechaza sistemas con data layer accesible desde internet independientemente de otros controles.

#### Impacto en estado actual de Recovery (cliente productivo)

**Riesgo real bajo pero no cero**. Postgres tiene password (`pg_password`, débil — otra deuda), Redis tiene password fuerte. No hay evidencia de explotación actual, pero la superficie de ataque está abierta al mundo. Los scanners automáticos (Shodan, Censys) eventualmente los indexan.

#### Fix planificado (mismo día)

Patrón: cambiar todos los mapeos `"PUERTO:PUERTO"` a `"127.0.0.1:PUERTO:PUERTO"` en los 3 compose files afectados:

- `/home/ubuntu/PQRS_V2/docker-compose.yml` (prod)
- `/home/ubuntu/PQRS_V2_STAGING/docker-compose.yml` (staging)
- `/opt/evolution-api/docker-compose.yml` (Evolution API)

Y hacer `docker compose up -d --no-deps <servicios>` en cada stack para recrear solo los containers afectados **sin rebuild**. Nginx sigue intacto en `0.0.0.0:443` porque es el punto de entrada legítimo y no se toca.

---

### Descubrimiento colateral: Evolution API en `/opt/evolution-api/`

Durante el diagnóstico se detectaron 3 containers `evolution_*` corriendo en paralelo al stack de FlexPQR, instalados en `/opt/evolution-api/` (fuera del directorio del proyecto PQRS_V2):

| Container | Imagen | Puerto | Volumen |
|---|---|---|---|
| `evolution_api` | `atendai/evolution-api:latest` | `:8080` (expuesto público) | `evolution_instances` (8K), `evolution_store` (4K) |
| `evolution_db` | `postgres:16-alpine` | Red interna | `evolution_pg_data` (47.4 MB con chats históricos) |
| `evolution_redis` | `redis:7-alpine` | Red interna | volumen anónimo |

**Origen**: Nico lo instaló hace ~5 semanas como experimento para probar integración WhatsApp, pero la sesión de WhatsApp cayó hace ~3 semanas y nunca se reconectó. Cero actividad en logs de las últimas 24h.

**Estado actual**: idle total. El container `evolution_api` sigue corriendo con `RestartPolicy: always` pero sin sesión WhatsApp conectada y sin integración activa con FlexPQR.

**Decisión tomada**: Evolution API sale del stack de FlexPQR. Si en el futuro se necesita WhatsApp, se usará **API oficial de Meta (WhatsApp Business Platform) con cuentas verificadas**, que es el único camino compatible con compliance bancario. Evolution API no es oficial de Meta (usa Baileys/WhatsApp Web) y los bancos no lo aceptan.

**Plan escalonado para Evolution API**:

1. **Hoy (como parte del fix de puertos)**: limitar `evolution_api:8080` a `127.0.0.1` con recreate aislado. El container sigue vivo, el volumen `pg_data` (47.4 MB) queda intacto, pero ya no hay leak público.
2. **Sesión dedicada futura**: backup del volumen `evolution_pg_data` (por si hay mensajes relevantes) + `docker compose down` completo del proyecto evolution-api + `docker volume rm` de los volúmenes + eliminación del directorio `/opt/evolution-api/`.
3. **Si alguna vez se necesita WhatsApp real**: implementar API oficial de Meta desde cero, **no** restaurar Evolution API.

---

### Deuda adicional descubierta: Bus factor de 1

Durante esta sesión se confirmó que **Nico Herrera es el único con acceso SSH al VPS de AWS** donde corre FlexPQR. Ni Martín Pallarés ni Dante Anelli ni Gabriel Cimas tienen acceso al server.

**Implicaciones**:

- **Compliance bancario**: el Punto 10 del análisis (Secure SDLC y control de cambios) exige segregación de funciones. La misma persona no puede ser desarrollador + operador + revisor de cambios + propietario de secretos. FlexFintech hoy no cumple este requisito.
- **Continuidad de negocio**: si Nico no puede trabajar (enfermedad, emergencia, vacaciones), no hay nadie que pueda acceder al server, hacer un fix, recuperar un backup, o reiniciar un servicio crítico. Esto es un deal-breaker de continuidad para cualquier banco serio.
- **Punto 11 del análisis** (Continuidad y exit plan) también se ve afectado: un plan de continuidad bancario exige **múltiples personas** con capacidad de operar el sistema.

**Acciones sugeridas para la reunión estratégica**:

1. **Designar un segundo operador** con acceso SSH al VPS, idealmente Dante o un contratista DevOps
2. **Rotar la key SSH** actual y generar una nueva con passphrase + distribución controlada a 2 personas
3. **Documentar runbooks operativos** para que alguien más pueda seguir instrucciones claras en caso de emergencia
4. **Separar cuentas en AWS IAM** con roles específicos por función (desarrollo, operación, auditoría)
5. **Incorporar esto al Punto 10 y al Punto 11 del análisis** como deuda crítica

**Responsable de esta acción**: Martín (es decisión organizacional/presupuestaria, no técnica).

---

### Hallazgo crítico: `MINIO_PUBLIC_URL` apunta a IP obsoleta

Durante la verificación previa al fix de puertos expuestos (14-abril-2026), se descubrió que el `docker-compose.yml` tiene configurada la variable:

```yaml
- MINIO_PUBLIC_URL=http://54.233.39.211:9020
```

en 2 servicios distintos (líneas 88 y 113). Pero la IP pública actual del server es `18.228.54.9`, no `54.233.39.211`. Son 2 IPs distintas.

#### Contexto técnico

La variable `MINIO_PUBLIC_URL` es usada por `backend/app/services/storage_engine.py` (líneas 92-93) para reemplazar el endpoint interno `minio:9000` en las URLs presigned que se le entregan al browser del usuario final para descargar adjuntos:

```python
if MINIO_PUBLIC_URL and url:
    url = url.replace(f"http://{MINIO_ENDPOINT}", MINIO_PUBLIC_URL, 1)
```

Esto significa que cuando un abogado de Recovery intenta descargar un adjunto de un caso, el backend genera una URL del tipo `http://54.233.39.211:9020/bucket/archivo...` — apuntando a una IP que ya no pertenece al servidor actual.

#### Escenarios posibles

1. **IP vieja apagada**: downloads de adjuntos están rotos desde la migración. Los operadores ven un error o timeout y posiblemente lo trabajaron por otras vías (email directo, WhatsApp, etc).
2. **IP vieja todavía viva**: por casualidad sigue respondiendo y los downloads funcionan por accidente. Riesgo: el día que esa IP se apague, todo se rompe sin aviso.
3. **Feature de adjuntos no usado en producción**: nadie usa la funcionalidad, por eso nadie notó el bug.

Se ejecutó query al audit log y tabla de adjuntos para confirmar cuál de los 3 escenarios aplica (ver resultado abajo en sección "Verificación de uso real").

#### Impacto en el fix de puertos de hoy

El fix de hoy (14-abril) cerrará los puertos `0.0.0.0:9020` y `0.0.0.0:9021` a `127.0.0.1` **solo como parte de una Fase B futura**, no hoy. MinIO queda con `ports:` intactos en esta sesión para evitar romper funcionalidad potencialmente en uso.

#### Plan de remediación propuesto (sesión dedicada futura)

1. **Investigar el estado real de la IP antigua** `54.233.39.211` — si sigue activa o no
2. **Corregir `MINIO_PUBLIC_URL`** en el `docker-compose.yml` a la IP correcta O mejor aún, a un dominio público del tipo `https://app.flexpqr.com/minio/...`
3. **Configurar Nginx como reverse proxy** hacia MinIO, exponiendo bajo HTTPS (cumple TLS requirement)
4. **Recrear el backend** con la nueva configuración
5. **Verificar que el download de adjuntos funciona** con un caso real de Recovery
6. **Una vez verificado, cerrar los puertos `:9020` y `:9021`** siguiendo el patrón de `127.0.0.1`
7. **Documentar el runbook** del proceso para futura referencia

#### Severidad

🟡 **Media**. No es deal-breaker inmediato (el feature de adjuntos es secundario al flujo principal de FlexPQR), pero refleja un gap de calidad operativa: hay configuración hardcodeada en un compose que quedó desalineada con el infra real sin que nadie lo detectara. Para un banco, esto indica "falta de control de cambios y gestión de config" (cruza con Punto 10 del análisis — Secure SDLC).

#### Verificación de uso real (ejecutada después de este append)

**Query al audit log y tabla de adjuntos (14-abril-2026)**:

| Métrica | Valor |
|---|---|
| Total adjuntos en DB (histórico) | **576** |
| Adjuntos últimos 30 días | **535** (93% del total) |
| Casos con adjuntos (últimos 30d) | **233** |
| Último adjunto registrado | **2026-04-14 16:57:16 UTC** (minutos antes de esta verificación) |
| Tenants que usan adjuntos | **FlexFintech** (448 totales, 94 últimos 7d) + **Abogados Recovery** (128 totales, 51 últimos 7d) |
| Tamaño volumen `pqrs_v2_minio_v2_data` | **399 MB** (bucket `pqrs-vault` con datos reales) |
| Audit log con acciones `%download%` / `%descarga%` / `%adjunto%` | **0 filas** (el sistema no registra descargas como eventos) |
| Logs del backend últimos 7d con `minio` / `adjunto` / `storage_engine` | **0 hits** (las operaciones de storage son silenciosas en logs) |

**Estado de la IP antigua `54.233.39.211`** (ejecutado desde el server actual):

- `ping -c 2`: **100% packet loss** (la IP no responde a ICMP)
- `curl -sI http://54.233.39.211:9020/`: **timeout / sin respuesta**
- `openssl s_client 54.233.39.211:443`: **sin respuesta**

**La IP vieja está muerta / inaccesible desde internet.**

**Conclusión — escenario mixto entre 1 y 3**:

- **Escenario 3 descartado**: el feature de adjuntos está **muy activo**. Se crearon 51 adjuntos en Recovery en los últimos 7 días, 94 en FlexFintech, el más reciente hace ~30 minutos antes de esta verificación. La tabla `pqrs_adjuntos` es 100% usada en producción y tiene 576 filas acumuladas que referencian archivos en el volumen de 399 MB.
- **Escenario 1 (IP vieja apagada, downloads rotos)** es el más probable para el **path de download vía `MINIO_PUBLIC_URL`**. La IP `54.233.39.211` está muerta, por lo que cualquier presigned URL que el backend genere (apuntando a esa IP) fallará en el browser del cliente.
- **La contradicción aparente** (upload activo + download roto vía MINIO_PUBLIC_URL) sugiere una de estas dos posibilidades:
  1. Los operadores de Recovery rara vez descargan sus propios adjuntos desde el UI — reciben los archivos directamente en los emails que procesan, los almacenan en MinIO como respaldo/trazabilidad, pero no los vuelven a descargar. El feature de upload es para **preservar evidencia**, no para **consulta activa**.
  2. Existe un mecanismo alternativo de download en el backend (streaming proxy vía `/api/v2/casos/{id}/adjuntos/{adj_id}/descargar` o similar) que NO usa `MINIO_PUBLIC_URL` y sí funciona. No lo verifiqué en esta sesión.

**Implicación para el fix de MinIO**:

🛑 **NO cerrar los puertos `:9020` y `:9021` en esta sesión.**

Razones:
1. El feature de adjuntos está **muy activo** (upload funciona, 576 archivos reales en 399 MB).
2. No sé con certeza si existe un mecanismo de download alternativo que use directamente `18.228.54.9:9020`. Cerrar el puerto sin verificarlo primero podría romper algo en caliente.
3. El tema de `MINIO_PUBLIC_URL` apuntando a IP muerta es una deuda pre-existente que **ya lleva tiempo sin que nadie se queje** — un día o dos más no cambia nada.
4. La sesión dedicada de remediación MinIO (el plan de 7 pasos de arriba) es el camino correcto: primero arreglar `MINIO_PUBLIC_URL` + Nginx reverse proxy + verificar downloads, después cerrar los puertos.

Se procede con el fix de los otros 9 puertos VERDE hoy, dejando MinIO (`:9020` + `:9021`) con `0.0.0.0:` intacto hasta la sesión dedicada.

#### Nota adjunta: el patrón se repite en Evolution API

Durante el Checkpoint 0 del fix de puertos (14-abril-2026, previo a la edición de `/opt/evolution-api/docker-compose.yml`), se descubrió que **el mismo patrón de IP obsoleta hardcodeada también existe en el compose de Evolution API**:

```yaml
# /opt/evolution-api/docker-compose.yml línea 38
environment:
  SERVER_URL: http://54.233.39.211:8080
```

El valor `54.233.39.211:8080` es la **misma IP vieja** que aparece en `MINIO_PUBLIC_URL`, confirmada como muerta (100% packet loss al ping desde el server actual). Evolution API usa `SERVER_URL` internamente para construir URLs públicas de QR codes de WhatsApp, webhooks salientes, y respuestas a clientes externos. Como la IP está muerta y Evolution API además perdió su sesión WhatsApp hace 3 semanas (ver sub-sección "Descubrimiento colateral: Evolution API" arriba), **este campo actualmente no afecta ningún flujo funcional**, pero es la segunda instancia del mismo antipatrón.

**Implicación**:

1. **No hay un único culpable puntual** del desalineamiento de IP — es un **patrón sistémico**: cuando el server prod migró de `54.233.39.211` a `18.228.54.9`, nadie ejecutó un barrido global de `grep -r "54.233.39.211"` en los archivos de configuración del server. Quedaron referencias residuales en al menos 2 lugares distintos.
2. **Probablemente hay más referencias obsoletas** en otros archivos que todavía no vimos: scripts de backup, env files (`.env`), configs de certbot, configs de IAM, configs de monitoreo, etc. Se recomienda hacer un `sudo grep -r "54.233.39.211" /home/ubuntu /opt /etc 2>/dev/null` en la sesión dedicada de remediación para descubrir el alcance total.
3. **Cruza con el Punto 10** del análisis (Secure SDLC + gestión de configuración): la ausencia de un mecanismo automático para detectar referencias a infraestructura obsoleta es una debilidad de calidad que un auditor bancario va a levantar.

**Acción en este fix**: **no se toca `SERVER_URL` del Evolution API**. Solo se modifican los `ports:` para cerrar el leak de `:8080` público. La corrección del `SERVER_URL` hardcoded queda como parte de la Fase B de remediación MinIO/Evolution.

---

### Fix ejecutado: 9 puertos expuestos cerrados a 127.0.0.1 (14-abril-2026, 17:57-18:15 UTC)

Después del diagnóstico documentado en las sub-secciones anteriores, se ejecutó el fix completo de 9 servicios expuestos públicamente. MinIO (`:9020` y `:9021`) quedó fuera del scope de hoy por decisión explícita: sesión dedicada futura para resolverlo correctamente con reverse proxy en Nginx + corrección del `MINIO_PUBLIC_URL` hardcoded. Adicionalmente, durante el fix se descubrió que MinIO `:9020/:9021` estaban filtrados por AWS Security Group, por lo que el riesgo real de exposición era menor al pensado inicialmente, aunque la deuda de configuración sigue.

#### Patrón aplicado

Cambio de mapeos en los archivos `docker-compose.yml` afectados, de:

```yaml
ports:
  - "PUERTO_HOST:PUERTO_CONTAINER"
```

a:

```yaml
ports:
  - "127.0.0.1:PUERTO_HOST:PUERTO_CONTAINER"
```

Y `docker compose up -d --no-deps <service>` por stack (sin rebuild de imágenes, solo recreate de containers).

#### Servicios afectados

| # | Stack | Container | Puerto antes | Puerto después | Estado post-fix |
|---|---|---|---|---|---|
| 1 | PQRS_V2 | pqrs_v2_backend | `0.0.0.0:8001` | `127.0.0.1:8001` | ✅ |
| 2 | PQRS_V2 | pqrs_v2_frontend | `0.0.0.0:3002` | `127.0.0.1:3002` | ✅ |
| 3 | PQRS_V2 | pqrs_v2_db | `0.0.0.0:5434` | `127.0.0.1:5434` | ✅ |
| 4 | PQRS_V2 | pqrs_v2_redis | `0.0.0.0:6381` | `127.0.0.1:6381` | ✅ |
| 5 | PQRS_V2_STAGING | pqrs_staging_backend | `0.0.0.0:8002` | `127.0.0.1:8002` | ✅ |
| 6 | PQRS_V2_STAGING | pqrs_staging_frontend | `0.0.0.0:3003` | `127.0.0.1:3003` | ✅ |
| 7 | PQRS_V2_STAGING | pqrs_staging_db | `0.0.0.0:5435` | `127.0.0.1:5435` | ✅ |
| 8 | PQRS_V2_STAGING | pqrs_staging_redis | `0.0.0.0:6382` | `127.0.0.1:6382` | ✅ |
| 9 | /opt/evolution-api | evolution_api | `0.0.0.0:8080` | `127.0.0.1:8080` | ✅ |

#### Archivos modificados

| Archivo | Cambios | Backup creado |
|---|---|---|
| `~/PQRS_V2/docker-compose.yml` | 4 mapeos | `docker-compose.yml.backup.20260414_175705` |
| `~/PQRS_V2_STAGING/docker-compose.staging.yml` | 4 mapeos | `docker-compose.staging.yml.backup.20260414_175705` |
| `/opt/evolution-api/docker-compose.yml` | 1 mapeo | `docker-compose.yml.backup.20260414_175705` |

#### Servicios NO tocados

| Servicio | Puerto | Motivo |
|---|---|---|
| `pqrs_v2_nginx` | `:443` | Es el punto de entrada legítimo del usuario |
| `pqrs_v2_minio` (API) | `:9020` | Sesión dedicada futura — depende de fix del `MINIO_PUBLIC_URL` |
| `pqrs_v2_minio` (consola) | `:9021` | Misma sesión dedicada futura |
| `pqrs_v2_master_worker` | (ninguno) | No tiene puertos publicados |
| `pqrs_v2_demo_worker` | (ninguno) | No tiene puertos publicados |
| `evolution_db` / `evolution_redis` | (red interna) | Ya estaban en red privada, sin puertos publicados |
| `kafka_staging` / `zookeeper_staging` / `minio_staging` | declarados pero containers no corriendo | No requiere acción |

#### Verificación post-fix

| Verificación | Resultado |
|---|---|
| 9 containers Up con mapping `127.0.0.1:*` | ✅ 9/9 |
| Listeners kernel en `127.0.0.1:*` (no `0.0.0.0`) | ✅ 9/9 |
| Puertos públicos cerrados desde IP externa (smoke test con `curl` y `bash /dev/tcp`) | ✅ 9/9 |
| `app.flexpqr.com` responde 200 OK por HTTPS | ✅ |
| Stack intacto (master_worker, nginx, minio, demo_worker, evolution_db/redis) sin afectación | ✅ 6/6 |
| Backend prod arranca sin errores nuevos (solo ruido Kafka pre-existente) | ✅ |
| Smoke test manual de Nico en navegador: Recovery operativo + demo operativo | ✅ |

#### Plan de rollback (disponible por 30 días)

Si se detecta algún problema en los próximos días que correlacione con el fix, los backups del 17:57:05 UTC permiten volver al estado anterior:

```bash
BACKUP_TS="20260414_175705"
cp ~/PQRS_V2/docker-compose.yml.backup.${BACKUP_TS} ~/PQRS_V2/docker-compose.yml
cp ~/PQRS_V2_STAGING/docker-compose.staging.yml.backup.${BACKUP_TS} ~/PQRS_V2_STAGING/docker-compose.staging.yml
sudo cp /opt/evolution-api/docker-compose.yml.backup.${BACKUP_TS} /opt/evolution-api/docker-compose.yml

cd ~/PQRS_V2 && docker compose up -d --no-deps backend_v2 frontend_v2 postgres_v2 redis_v2
cd ~/PQRS_V2_STAGING && docker compose -f docker-compose.staging.yml up -d --no-deps backend_staging frontend_staging postgres_staging redis_staging
cd /opt/evolution-api && sudo docker compose up -d --no-deps evolution-api
```

#### Hallazgo bonus durante la verificación

Los puertos de MinIO (`:9020` y `:9021`) **estaban filtrados por AWS Security Group** desde antes de este fix, según hallazgo del agente durante la verificación. Esto significa que el riesgo real de exposición de MinIO era menor al pensado inicialmente: los puertos estaban "publicados" en `0.0.0.0` por Docker pero bloqueados a nivel de firewall AWS.

**Implicación**: la configuración de AWS Security Group existe y filtra parcialmente. **Acción pendiente**: documentar el estado completo del Security Group como parte del Punto 3 (Arquitectura cloud aceptable para banca) y validar que no hay reglas demasiado permisivas. Esto es deuda nueva registrada.

#### Estado de seguridad post-fix

**Antes del fix**: 11 servicios internos visibles desde internet con `nmap 18.228.54.9`.

**Después del fix**: solo `:443` (Nginx HTTPS) visible públicamente. Los 9 servicios cerrados + los 2 de MinIO (filtrados por SG) ya no son detectables externamente.

**Resultado neto**: el deal-breaker bancario más obvio del diagnóstico de seguridad fue cerrado. Esto no significa que FlexPQR cumpla con todos los requisitos de Banco Popular, pero sí que pasa el primer filtro técnico que cualquier auditor ejecutaría en la etapa inicial de due diligence.

---

---

## Punto 3 — Arquitectura cloud aceptable para banca

### Estado actual
- 1 instancia EC2 t3.large en sa-east-1 (`18.228.54.9`), single-AZ, single-region
- AWS Security Group existe y filtra parcialmente (descubierto durante el fix de puertos)
- Sin VPC dedicada documentada (probablemente la default de AWS)
- Sin balanceador (ALB/NLB) — el tráfico va directo al EC2
- Sin auto-scaling, sin réplicas, sin HA real
- CloudWatch básico activo (vía monitor cron)
- Backups diarios a S3 con versionado + lifecycle (esto sí está bien)

### Gap identificado
1. Multi-AZ deployment (mínimo 2 zonas de disponibilidad para HA)
2. Application Load Balancer entre internet y EC2 (TLS termination + WAF)
3. WAF (AWS WAF o equivalente) para reglas de protección de aplicación
4. VPC dedicada con subnets públicas/privadas (DB y backend en privada, ALB en pública)
5. Documentación formal de arquitectura cloud con diagrama y justificaciones
6. Hardening del Security Group revisado regla por regla
7. Encryption at rest verificado en EBS volumes y S3 buckets
8. VPC Flow Logs activados para auditoría de tráfico

### Esfuerzo estimado
- **Quick wins (1-2 días):** revisar Security Group, activar VPC Flow Logs, verificar encryption at rest, documentar arquitectura actual
- **Mejoras moderadas (1-2 semanas):** ALB + WAF básico + redistribución a VPC privada
- **Migración completa a multi-AZ con HA:** 4-8 semanas de proyecto dedicado, requiere migración de DB a RDS Multi-AZ o similar
- **Costo AWS adicional estimado:** USD 200-500/mes adicionales por la infra HA

### Responsable sugerido
- **Nico:** quick wins de Security Group + documentación
- **Externo (DevOps/SRE):** migración a HA — requiere par de manos especializado

### Camino A / B / C — relevancia
- **Camino A (SaaS certificado):** CRÍTICO. Sin HA multi-AZ no se puede vender SaaS bancario. Es prerequisito.
- **Camino B (on-premise en banco):** NO APLICA. La infra la pone el banco.
- **Camino C (híbrido):** CRÍTICO para los clientes SaaS, no para los on-premise.

### Quick win posible esta semana
Documentar el estado actual del Security Group (qué reglas existen, qué puertos permiten, qué CIDRs) y activar VPC Flow Logs (5 minutos en consola AWS, gratis en el primer mes).

---

## Punto 4 — IAM (gestión de identidades y accesos)

### Estado actual
- Multi-tenancy con RLS + RBAC en Postgres ✅ (ya implementado)
- JWT para autenticación de aplicación (TTL 480 min)
- Bcrypt para passwords (estándar correcto)
- Roles dentro de la app: admin, operador, supervisor (definidos en el sistema)
- AWS IAM: un único usuario root (Nico) con acceso completo
- SSH al VPS: una única key (Nico), sin passphrase, sin segundo operador
- MFA en consola AWS: desconocido (probable que no esté activo)
- MFA en la app FlexPQR: no implementado
- SSO (Azure AD via Gabi Cimas): mencionado pero no implementado

### Gap identificado
1. MFA obligatorio en AWS root + IAM users (mínimo bancario)
2. MFA en FlexPQR app para usuarios admin
3. Segregación de roles AWS: crear IAM users separados (dev, ops, audit) con políticas mínimas
4. SSO (Azure AD) para login en FlexPQR
5. Audit log de accesos AWS (CloudTrail activado y exportado a S3)
6. Política formal de gestión de identidades con ciclo (alta, baja, modificación, revisión periódica)
7. Bus factor de 1 en SSH (deuda ya documentada — se cruza con este punto)

### Esfuerzo estimado
- **Quick wins (1 día):** activar MFA en AWS, activar CloudTrail, crear IAM users segregados con políticas
- **MFA en FlexPQR app (2-3 semanas):** desarrollo + UI + flujo de recuperación
- **SSO con Azure AD (1-2 meses):** integración OIDC/SAML, depende de Gabi Cimas + tenant Azure ya configurado
- **Política formal:** parte del consultor de seguridad del Punto 1

### Responsable sugerido
- **Nico:** MFA AWS + IAM segregado + CloudTrail (esta semana, 2-3 horas)
- **Nico + Gabi Cimas:** SSO Azure AD (proyecto dedicado)
- **Consultor (Punto 1):** política formal

### Camino A / B / C — relevancia
- **Camino A:** CRÍTICO. MFA + SSO no son negociables.
- **Camino B:** PARCIAL. SSO se hace con el AD del banco. MFA AWS sigue siendo necesario para el equipo de FlexFintech.
- **Camino C:** CRÍTICO para SaaS, PARCIAL para on-premise.

### Quick win posible esta semana
Activar MFA en cuenta root de AWS + crear IAM user separado para deploys (no usar root) + activar CloudTrail con log a S3. Total: 30-60 minutos.

---

## Punto 5 — Protección de datos (cifrado, retención, eliminación)

### Estado actual
- TLS 1.2/1.3 en Nginx público ✅ (verificado en este análisis)
- Cifrado en reposo de Postgres: desconocido (probable que el volumen EBS esté cifrado por default si fue creado en sa-east-1 reciente, pero no está confirmado)
- Cifrado en reposo de MinIO: desconocido (configurable pero no verificado)
- Cifrado en reposo de Redis: no aplica para datos persistentes (pero sí para AOF/RDB si activo)
- Backups en S3: versionado activo, encryption SSE-S3 por default (buena base, pero no SSE-KMS con CMK)
- Audit log de respuestas: existe (`audit_log_respuestas`)
- Retención de datos: no hay política formal escrita
- Eliminación segura: procedimiento informal (DELETE en SQL, sin secure-erase del backup)
- Archivos adjuntos en MinIO: sin cifrado object-level documentado

### Gap identificado
1. Política formal de retención (ej: PQRS conservadas 10 años, audit logs 7 años — alineado con SARLAFT)
2. Verificar y forzar encryption at rest en EBS, S3, MinIO
3. KMS (Key Management Service) con keys propias (CMK) en lugar de SSE-S3 default
4. Cifrado de Postgres a nivel columna para campos sensibles (ej: identificación del peticionario)
5. Procedimiento documentado de eliminación segura al terminar contrato (right to be forgotten)
6. DLP (Data Loss Prevention) y/o watermarking en respuestas con datos personales — Bancolombia lo pide explícitamente
7. Clasificación de datos (público/interno/confidencial/restringido) con marcado en la UI

### Esfuerzo estimado
- **Verificación de encryption at rest (1 día):** mirar config actual de EBS, S3, MinIO, decidir si pasar a KMS
- **KMS con CMK propia (2-3 días):** crear key, rotar usos
- **Política de retención y eliminación (1-2 semanas):** redacción + implementación de jobs automatizados de purga
- **DLP / watermarking (4-6 semanas de desarrollo):** dependiendo de complejidad
- **Cifrado a nivel columna (3-4 semanas):** invasivo en código

### Responsable sugerido
- **Nico:** verificación de encryption + KMS (1-2 días)
- **Consultor (Punto 1):** política formal de retención
- **Nico + dev frontend:** DLP / watermarking (proyecto)

### Camino A / B / C — relevancia
- **Camino A:** CRÍTICO todo el stack
- **Camino B:** PARCIAL — el banco define muchos de estos controles, FlexPQR solo cumple los aplicables a la app
- **Camino C:** CRÍTICO para SaaS, NEGOCIABLE para on-premise

### Quick win posible esta semana
Auditar el estado actual de encryption at rest (3 comandos AWS CLI: ver volúmenes EBS, ver buckets S3, ver políticas KMS) y documentar el resultado. Si algo no está cifrado, activarlo en menos de 30 minutos.

---

## Punto 6 — Ubicación de datos / subprocesadores

### Estado actual
- EC2 prod en sa-east-1 (São Paulo, Brasil) — datos físicamente en Brasil, no en Colombia
- S3 backups en sa-east-1 — mismo país, Brasil
- Subprocesadores activos identificados:
  - **AWS** (infraestructura: EC2, S3, CloudWatch) — datos en Brasil
  - **Anthropic Claude API** (clasificación IA + generación de respuestas) — datos en USA, modelos en regiones AWS US
  - **Zoho Mail** (envío de emails) — servidores en USA + India + Europa según plan
  - **Cloudflare** (si está en uso para DNS / CDN) — global
- Sin lista formal de subprocesadores comunicada a clientes
- Sin acuerdos de transferencia internacional de datos firmados con clientes (DPA con cláusulas de transferencia)

### Gap identificado
1. Lista formal de subprocesadores publicada en `flexpqr.com/subprocesadores` o entregada a clientes
2. Cláusulas contractuales tipo (CCT) o equivalente de Habeas Data Colombia para transferencia internacional
3. Consentimiento explícito del titular del dato para envío a Anthropic (USA) — texto en política de privacidad de Recovery
4. Política de no-uso de datos para entrenamiento — verificar que Anthropic no use los prompts para entrenar modelos (la API enterprise ya lo garantiza, hay que confirmar)
5. Migración de prod a otra región es decisión estratégica: algunos bancos colombianos prefieren datos en territorio nacional, pero AWS no tiene región en Colombia (la más cercana es sa-east-1 Brasil que es lo que hay)
6. Documentación de flujo de datos transfronterizo — qué dato sale, a qué proveedor, con qué propósito

### Esfuerzo estimado
- **Lista de subprocesadores (1 día):** redacción + publicación en sitio web
- **CCT / cláusulas de transferencia (parte del consultor + abogado del Punto 1-2)**
- **Verificación con Anthropic sobre no-uso para entrenamiento (1 hora):** revisar términos, confirmar plan API sin entrenamiento
- **Política de privacidad actualizada (parte del trabajo legal del Punto 2)**

### Responsable sugerido
- **Nico:** lista técnica de subprocesadores + verificación Anthropic
- **Abogado externo (Punto 2):** CCT y política de privacidad
- **Martín:** decisión estratégica de región AWS si algún banco lo exige

### Camino A / B / C — relevancia
- **Camino A:** CRÍTICO. Lista de subprocesadores es lo primero que pide cualquier banco
- **Camino B:** PARCIAL. Si el banco corre FlexPQR en su propia AWS o on-premise, la lista cambia
- **Camino C:** CRÍTICO para SaaS, PARCIAL para on-premise

### Quick win posible esta semana
Hacer la lista de subprocesadores en una página markdown (`Brain/SUBPROCESADORES_FLEXPQR.md`) con: nombre, propósito, ubicación, datos compartidos, base legal. 1 hora de trabajo.

---

## Punto 7 — Conectividad segura

### Estado actual
- TLS 1.2/1.3 en Nginx público ✅
- Certificado Let's Encrypt con renovación automática hasta 17-jun-2026 ✅
- Conexiones a Anthropic API: HTTPS estándar, API key estática (sin rotación documentada)
- Conexiones a Zoho Mail: OAuth2 con refresh token (mejor que API key estática)
- Conexiones internas Docker: HTTP plano dentro de la red bridge (no TLS) — aceptable porque está en localhost, pero un auditor estricto puede objetar
- Sin VPN site-to-site con ningún cliente actual
- Sin IP whitelisting documentado del lado FlexPQR (cualquier IP puede llegar a Nginx :443)
- Webhooks salientes (si los hay): desconocido, posiblemente Evolution API tenía esto
- Sin política de rotación de credenciales documentada

### Gap identificado
1. Rotación documentada de credenciales (Anthropic API key, Zoho OAuth, AWS keys) cada 90 días
2. mTLS interno entre containers Docker (opcional pero valorado por bancos estrictos)
3. VPN site-to-site con clientes bancarios (cuando se firme el primer contrato bancario)
4. IP whitelisting bidireccional — banco solo puede acceder desde IPs declaradas, FlexPQR solo se conecta a IPs del banco declaradas
5. WAF (cruza con Punto 3) — mitigar OWASP Top 10 a nivel red
6. Certificate pinning en clientes críticos (futuro)
7. Inventario de todas las conexiones salientes del backend (qué llama a qué externamente)

### Esfuerzo estimado
- **Rotación de credenciales (2-3 días):** scripts + documentación de procedimiento
- **Inventario de conexiones salientes (4 horas):** revisar código + ENV vars
- **VPN site-to-site (cuando se firme contrato bancario):** 1-2 semanas con el equipo de redes del banco
- **mTLS interno (4-6 semanas):** invasivo, requiere cambios en cada servicio

### Responsable sugerido
- **Nico:** rotación de credenciales + inventario
- **Nico + equipo redes del banco:** VPN cuando aplique
- **mTLS:** sesión dedicada, baja prioridad hoy

### Camino A / B / C — relevancia
- **Camino A:** MEDIO. TLS público ya está OK, lo que falta son procedimientos formales (rotación, IP whitelisting)
- **Camino B:** CRÍTICO. Si el banco te pide deploy on-premise, vas a necesitar VPN al equipo de FlexFintech para mantenimiento + procedimientos de rotación
- **Camino C:** MEDIO en ambas variantes

### Quick win posible esta semana
Hacer un inventario de credenciales activas (Anthropic, Zoho, AWS, GitHub, Vercel) con: cuándo fue rotada por última vez, dónde está almacenada, quién tiene acceso. 1 hora.

---

## Punto 8 — Logs e incidentes

### Estado actual
- Audit log de respuestas (`audit_log_respuestas`) activo en Postgres ✅
- Logs aplicativos del backend en stdout de container (rotación Docker default)
- CloudWatch básico activo via cron monitor, pero limitado a métricas de containers
- Sin SIEM (Sistema de gestión de eventos de seguridad)
- Sin agregación centralizada de logs (cada container tiene los suyos en local)
- Sin alertamiento configurado ante eventos críticos (cero notificaciones a Nico cuando algo se rompe)
- Sin política de retención de logs documentada
- Sin procedimiento de incident response escrito
- Sin clasificación de severidad de incidentes
- Sin runbook de respuesta para incidentes comunes

### Gap identificado
1. Centralización de logs (CloudWatch Logs, ELK, Loki, Datadog, o similar)
2. Retención de logs mínimo 7 años para audit logs (alineado SARLAFT)
3. Alertamiento automático:
   - Backend caído > 1 minuto
   - DB con conexiones colgadas
   - Errores 5xx > umbral
   - Acciones administrativas inusuales (logins fuera de horario, cambios masivos)
4. SIEM o equivalente para correlación de eventos (puede ser AWS GuardDuty + CloudTrail como base mínima)
5. Política de incident response con: clasificación severidad, tiempos de notificación al banco, plantillas de comunicación
6. Runbooks para los 10 incidentes más probables
7. Post-mortem template para incidentes mayores
8. Notificación obligatoria al banco dentro de 24-72hs ante incidente que afecte sus datos (requisito SFC)

### Esfuerzo estimado
- **Centralización a CloudWatch Logs (2-3 días):** configurar drivers Docker, costo AWS bajo
- **Alertamiento básico (3-5 días):** definir umbrales + configurar alarmas + integrar con notificación (email/Slack/PagerDuty)
- **Política formal de incident response (parte del consultor del Punto 1)**
- **Runbooks (proyecto continuo):** 1 runbook por semana, 10 semanas
- **GuardDuty + CloudTrail (1 día):** activar + configurar destinos

### Responsable sugerido
- **Nico:** centralización + alertamiento + runbooks
- **Consultor (Punto 1):** política formal + clasificación de severidad
- **Martín:** decisión sobre proveedor SIEM (gasto recurrente)

### Camino A / B / C — relevancia
- **Camino A:** CRÍTICO. Sin SIEM y sin incident response no hay banca posible
- **Camino B:** CRÍTICO también, el banco exige que FlexFintech cumpla estos requisitos sobre su propio sistema aunque corra en su infra
- **Camino C:** CRÍTICO en ambos

### Quick win posible esta semana
Activar **CloudTrail + GuardDuty** en AWS (10 minutos en consola, costo USD 5-15/mes en escala chica). Te da inmediatamente: audit log de toda acción AWS + detección automática de comportamiento anómalo. Es el primer paso barato hacia un SIEM.

---

## Punto 9 — Vulnerabilidades (gestión, escaneo, parchado)

### Estado actual
- Sin escaneo automatizado de vulnerabilidades en código ni infraestructura
- Sin pentesting realizado nunca al producto
- Dependencias Python: `requirements.txt` sin lockfile estricto, sin Dependabot/Renovate activo
- Dependencias Node.js (frontend): `package-lock.json` existe pero sin alertas automatizadas de CVE
- Imágenes Docker: versiones específicas en algunas (`postgres:15`, `redis:7-alpine`), pero `evolution-api:latest` y otras pueden tener drift
- Sin escaneo de imágenes (Trivy, Snyk, Docker Scout)
- SO del host EC2: Ubuntu, sin política de patching automatizado documentado
- Sin inventario de software (SBOM) del producto

### Gap identificado
1. Escaneo automatizado de dependencias (Dependabot en GitHub, gratis)
2. Escaneo de imágenes Docker (Trivy en CI, gratis)
3. Escaneo SAST del código (CodeQL en GitHub, gratis para repos públicos / pago para privados)
4. Pentesting anual por empresa externa (USD 5-15k por engagement)
5. Política formal de parchado con SLA: críticas 24-72hs, altas 7 días, medias 30 días, bajas 90 días
6. SBOM (Software Bill of Materials) generado automáticamente para cada release
7. Patching automático del SO del host (`unattended-upgrades` en Ubuntu) o procedimiento manual documentado
8. Monitoreo continuo de CVE publicados que afecten al stack
9. Pinear todas las imágenes Docker a versiones específicas (eliminar `:latest`)

### Esfuerzo estimado
- **Dependabot + Trivy + CodeQL en GitHub Actions (1-2 días):** configuración inicial
- **Pinear imágenes Docker (2 horas):** revisar compose files + cambiar `:latest` por versiones específicas
- **Política formal de patching (parte del consultor del Punto 1)**
- **Pentesting anual (proyecto recurrente):** 4-6 semanas con la empresa elegida, USD 5-15k/año
- **`unattended-upgrades` en Ubuntu (30 minutos):** activar + configurar reboots controlados

### Responsable sugerido
- **Nico:** Dependabot + Trivy + pinear imágenes + unattended-upgrades (esta semana, 4-6 horas)
- **Martín:** decisión comercial sobre pentesting (presupuesto)
- **Empresa externa:** pentesting cuando se contrate

### Camino A / B / C — relevancia
- **Camino A:** CRÍTICO. Pentesting + escaneo continuo es exigencia bancaria estándar.
- **Camino B:** CRÍTICO también, el banco te va a pedir reportes periódicos de vulnerabilidades aunque corra en su infra.
- **Camino C:** CRÍTICO en ambos

### Quick win posible esta semana
Activar **Dependabot** en el repo de GitHub (5 minutos en Settings → Security) + agregar **Trivy** como step en GitHub Actions (30 minutos). Te da escaneo automatizado de dependencias y de imágenes Docker. Gratis.

---

## Punto 10 — Secure SDLC (control de cambios, segregación de funciones)

### Estado actual
- Branches `develop → staging → main` existen como pipeline conceptual ✅
- **Nico es el único developer y el único operador** — bus factor de 1 (deuda crítica ya documentada)
- Pull Requests: existen pero Nico las crea y mergea solo (no hay code review real)
- CI/CD: parcialmente activo en GitHub Actions, sin escaneos de seguridad
- Tests automáticos: existen algunos pero cobertura desconocida
- Secrets management: archivos `.env` en el server + variables hardcodeadas en docker-compose.yml (descubierto durante el fix del FirmaModal)
- Audit trail de deploys: parcial (git log + Docker logs), no centralizado
- Sin separación de roles formal (dev, ops, audit son la misma persona)

### Gap identificado
1. Segundo desarrollador/operador mínimo para code review + segregación de funciones
2. Branch protection rules en GitHub (require PR review, require CI pass, require signed commits)
3. Code review obligatorio antes de merge a `main`
4. Secrets manager (AWS Secrets Manager o HashiCorp Vault) en lugar de `.env` files + hardcoded en compose
5. CI/CD pipeline completo con: lint + tests + escaneo de vulnerabilidades + escaneo de imágenes + deploy controlado
6. Audit trail centralizado de deploys (quién deployeó qué, cuándo, qué cambió)
7. Política formal de gestión de cambios con clasificación (estándar, normal, emergencia) y aprobaciones
8. Procedimiento de rollback documentado y probado periódicamente
9. Ambiente de pre-producción estable (staging hoy a veces drift respecto a prod)

### Esfuerzo estimado
- **Branch protection (15 minutos):** configurar en GitHub
- **Migración de `.env` a Secrets Manager (1-2 semanas):** invasivo, requiere refactor
- **CI/CD completo (1-2 semanas):** escribir workflows + integrar escaneos
- **Segundo operador (decisión comercial):** USD 2-5k/mes contratista DevOps o desarrollador semi-senior
- **Política formal de cambios (parte del consultor del Punto 1)**

### Responsable sugerido
- **Nico:** branch protection + CI/CD (esta y próxima semana)
- **Martín:** decisión sobre segundo operador (presupuesto + perfil)
- **Nico + segundo operador (cuando exista):** Secrets Manager + procedimientos formales

### Camino A / B / C — relevancia
- **Camino A:** 🚨 DEAL-BREAKER ABSOLUTO. Sin segregación de funciones no se firma con ningún banco serio.
- **Camino B:** 🚨 CRÍTICO también. El banco no acepta que una sola persona maneje todo el sistema que toca sus datos.
- **Camino C:** 🚨 DEAL-BREAKER en ambos.

### Quick win posible esta semana
Activar **branch protection rules** en `main` y `staging`: requerir PR + 1 review + CI verde antes de merge. Sin un segundo desarrollador hoy, Nico puede simular code review con un PR template que obligue a pasar checklist antes de auto-aprobarse. No es perfecto pero crea audit trail. 30 minutos.

### 🚨 ANCLAJE CRÍTICO PARA REU CON MARTÍN

Este es el Punto más importante de toda esta sesión. La frase para llevar a la reu:

> "El bus factor de 1 es deal-breaker bancario. Antes de firmar con Banco Popular o Bancolombia, FlexFintech necesita un segundo desarrollador/operador con acceso al VPS y conocimiento del sistema. Esto no es un capricho técnico, es un requisito formal de compliance bancario que el mismo mail de Dante reconoce como Punto 10."

---

## Punto 11 — Continuidad y exit plan

### Estado actual
- Backups diarios a S3 con versionado + lifecycle 30 días ✅
- Sin DR testeado — backups existen pero **nunca se probó restaurar de cero**
- Sin RTO/RPO definidos formalmente
- Sin plan de continuidad escrito
- Single point of failure en múltiples niveles: 1 server, 1 desarrollador, 1 región
- Sin exit plan para clientes
- Sin procedimiento de devolución/destrucción de datos al terminar contrato

### Gap identificado
1. Test de restore real — bajar la DB de prod a un EC2 nuevo desde un backup S3 y verificar integridad. Mínimo trimestral.
2. RTO/RPO por servicio documentados:
   - Backend down → RTO 4 horas (estimado actual)
   - DB perdida → RPO 24 horas (último backup), RTO 8 horas (restore)
   - Servidor entero perdido → RTO 24-48 horas (provisionar EC2 nuevo + restore)
3. DR site en otra región o al menos otra AZ
4. Plan formal de continuidad con roles, contactos, procedimientos
5. Exit plan para clientes:
   - Plazo de devolución de datos (ej: 30 días post-terminación)
   - Formato de exportación (SQL dump + CSV + adjuntos en ZIP)
   - Procedimiento de destrucción segura post-devolución
   - Certificado de destrucción firmado
6. Procedimiento de comunicación al banco ante incidente de continuidad

### Esfuerzo estimado
- **Test de restore (1 día):** primera vez, después automatizable
- **Documentar RTO/RPO actuales (4 horas):** análisis + redacción
- **DR site (proyecto, 4-8 semanas):** depende de Camino A vs B
- **Plan formal y exit plan (parte del consultor + abogado del Punto 1-2)**

### Responsable sugerido
- **Nico:** test de restore + RTO/RPO actuales
- **Nico + segundo operador:** DR site cuando exista
- **Consultor (Punto 1) + abogado (Punto 2):** plan formal + exit plan contractual

### Camino A / B / C — relevancia
- **Camino A:** CRÍTICO. Bancos exigen DR + exit plan formal.
- **Camino B:** MEDIO. Si el banco corre la infra, ellos hacen DR; FlexPQR solo aporta el exit plan de la app.
- **Camino C:** CRÍTICO para SaaS, MEDIO para on-premise.

### Quick win posible esta semana
Hacer el primer **test de restore real**: levantar un EC2 t3.medium temporal, descargar el último backup desde S3, restaurar la DB, validar que los datos están íntegros. 4-6 horas de trabajo. Si funciona: confirma RTO ~8h. Si no funciona: hallazgo crítico que hay que resolver antes de cualquier conversación bancaria.

---

## Punto 12 — Assurance externo (ISO 27001, SOC 2)

### Estado actual
- Sin certificación alguna (esperable para una startup early-stage)
- Sin SGSI implementado (cruza con Punto 1)
- Sin auditoría externa de seguridad realizada nunca

### Gap identificado
1. **ISO 27001:** certificación formal del SGSI. Plazo típico 12-18 meses desde implementación. Costo USD 30-80k entre consultor + auditor + mantenimiento anual.
2. **SOC 2 Type II:** más rápida de obtener (6-12 meses). Costo USD 25-60k. Más valorada por empresas SaaS que por bancos colombianos.
3. **ISO 27017 / 27018:** específicas de cloud y datos personales. Complementan ISO 27001.
4. **Alternativa intermedia:** assessment de seguridad por consultor reconocido (sin certificación formal pero con reporte). Costo USD 5-15k. Útil mientras se camina hacia certificación formal.

### Esfuerzo estimado
- **ISO 27001 (12-18 meses, USD 30-80k):** proyecto mayor
- **SOC 2 Type II (6-12 meses, USD 25-60k):** alternativa
- **Assessment intermedio (1-2 meses, USD 5-15k):** camino pragmático para empezar

### Responsable sugerido
- **Martín:** decisión comercial 100%. Es inversión grande, requiere business case y aprobación de inversores eventualmente.
- **Consultor de seguridad (Punto 1):** facilita el proceso

### Camino A / B / C — relevancia
- **Camino A:** MUY RECOMENDABLE. Algunas RFP bancarias requieren ISO 27001 como prerequisito de oferta.
- **Camino B:** NEGOCIABLE. Si el banco te integra a su SGSI, su certificación cubre la operación. FlexPQR aporta evidencia de controles propios.
- **Camino C:** MUY RECOMENDABLE para SaaS, NEGOCIABLE para on-premise.

### Quick win posible esta semana
Ninguno técnico. Pero estratégicamente: preparar un **business case de 1 página** para Martín con: opciones (assessment intermedio / SOC 2 / ISO 27001), costos, plazos, retorno (qué bancos lo exigen, qué clientes habilita).

---

## Punto 13 — Especiales (PCI DSS, Open Finance Colombia)

### Estado actual
- **PCI DSS: NO APLICA hoy.** FlexPQR no procesa datos de tarjetas de pago (no es procesador de pagos). Si en el futuro se integra con un gateway de pagos, sí aplicaría.
- **Open Finance Colombia:** NO APLICA directamente porque FlexPQR no es entidad financiera ni proveedor de servicios de iniciación de pago / información de cuenta. Pero sí es relevante indirectamente si los bancos clientes piden integración con sus APIs de Open Finance para enriquecer respuestas a PQRS.

### Gap identificado
1. **PCI DSS:** sin acción mientras no se procesen tarjetas. Si Martín considera agregar facturación con tarjeta para clientes B2B, evaluar entonces.
2. **Open Finance Colombia:**
   - Documentar que FlexPQR no es entidad obligada del régimen
   - Documentar capacidad técnica de integrar con APIs Open Finance del banco si lo requiere (consumir, no proveer)
   - Revisar requisitos contractuales que el banco pueda imponer derivados de su propia condición de obligado

### Esfuerzo estimado
- **PCI DSS:** N/A hoy. Si aplica futuro, USD 20-50k + 6-12 meses
- **Documentar posición Open Finance (4-8 horas):** redacción + revisión legal

### Responsable sugerido
- **Abogado externo (Punto 2):** documentar posición Open Finance y obligaciones derivadas
- **Nico:** capacidad técnica de integrar APIs externas (ya existe el patrón con Anthropic + Zoho, es replicable)

### Camino A / B / C — relevancia
- **Camino A:** BAJO salvo evolución de scope del producto
- **Camino B:** BAJO mismo
- **Camino C:** BAJO

### Quick win posible esta semana
Redactar 1 párrafo formal: *"FlexPQR no es entidad obligada del régimen de Open Finance Colombia (Decreto 1297/2022). FlexPQR opera como procesador de comunicaciones (PQRS) y no procesa información de cuentas, transacciones, ni servicios de pago. FlexPQR puede integrarse con APIs Open Finance del banco cliente bajo acuerdo específico para enriquecer respuestas a peticiones."*

---

## 🎯 Resumen ejecutivo del análisis

### Tabla maestra de severidad por punto

| # | Punto | Severidad | Camino A | Quick win esta semana |
|---|---|---|---|---|
| 1 | Gobierno seguridad | 🔴 Crítico | Prerequisito | No (decisión comercial) |
| 2 | Contratos B2B | 🔴 Crítico | Prerequisito | No (decisión comercial) |
| 3 | Arquitectura cloud | 🔴 Crítico | Prerequisito | ✅ Documentar SG + activar VPC Flow Logs |
| 4 | IAM | 🔴 Crítico | Prerequisito | ✅ MFA AWS + IAM users segregados + CloudTrail |
| 5 | Protección de datos | 🔴 Crítico | Prerequisito | ✅ Auditar encryption at rest |
| 6 | Subprocesadores | 🟡 Medio-Alto | Prerequisito | ✅ Lista de subprocesadores |
| 7 | Conectividad | 🟡 Medio | Procedimientos | ✅ Inventario credenciales + plan rotación |
| 8 | Logs e incidentes | 🔴 Crítico | Prerequisito | ✅ Activar GuardDuty |
| 9 | Vulnerabilidades | 🔴 Crítico | Prerequisito | ✅ Dependabot + Trivy + pinear imágenes |
| 10 | SDLC + bus factor | 🚨 Deal-breaker | **DEAL-BREAKER** | ✅ Branch protection (parcial) |
| 11 | Continuidad / DR | 🔴 Crítico | Prerequisito | ✅ Test de restore real |
| 12 | Assurance ISO/SOC | 🟡 Medio-Alto | Muy recomendable | No (business case) |
| 13 | PCI / Open Finance | 🟢 Bajo | No aplica hoy | ✅ Redactar posición Open Finance |

### Quick wins consolidados (próxima semana)

12 acciones con tiempo total estimado de ~10-15 horas:

1. ✅ Documentar AWS Security Group actual (Punto 3)
2. ✅ Activar VPC Flow Logs (Punto 3)
3. ✅ Activar MFA AWS root + crear IAM user separado para deploys (Punto 4)
4. ✅ Activar CloudTrail con destino S3 (Punto 4)
5. ✅ Auditar encryption at rest en EBS + S3 (Punto 5)
6. ✅ Lista de subprocesadores en `Brain/SUBPROCESADORES_FLEXPQR.md` (Punto 6)
7. ✅ Inventario de credenciales activas + plan de rotación trimestral (Punto 7)
8. ✅ Activar GuardDuty (Punto 8)
9. ✅ Configurar Dependabot + Trivy en GitHub Actions (Punto 9)
10. ✅ Pinear todas las imágenes Docker a versiones específicas (Punto 9)
11. ✅ Activar branch protection rules en main y staging (Punto 10)
12. ✅ Test de restore real desde S3 backup (Punto 11)
13. ✅ Redactar posición formal sobre Open Finance Colombia (Punto 13)

### Decisiones comerciales para reunión estratégica con Martín y Dante

| Decisión | Costo estimado | Responsable | Urgencia |
|---|---|---|---|
| 🚨 Segundo desarrollador/operador (bus factor) | USD 2-5k/mes | Martín | INMEDIATA |
| Consultor de seguridad (Punto 1) | USD 3-8k one-shot | Martín | Alta |
| Abogado B2B (Punto 2) | USD 2-5k one-shot | Martín | Alta |
| Pentesting anual (Punto 9) | USD 5-15k/año | Martín | Media |
| Assurance externo (Punto 12) | USD 5-15k assessment / USD 25-80k certificación | Martín | Media |
| Camino A vs B vs C | N/A — define todo lo demás | Martín + Dante + Nico | INMEDIATA |

### Inversión total estimada para "FlexPQR vendible a banca"

- **Mínimo viable** (assessment + abogado + consultor + segundo operador 6 meses): **USD 20-30k**
- **Camino A serio** (todo + ISO 27001 + pentesting + 1 año de operación con segundo dev): **USD 80-150k**

### Conclusión del análisis

El producto FlexPQR tiene **bases técnicas sólidas** (multitenancy con RLS, audit logs, backups, cifrado en tránsito) pero **gaps significativos en gobierno, procedimientos formales, y madurez operativa**. El **bus factor de 1** es el deal-breaker más urgente. La inversión necesaria es razonable y proporcional a la oportunidad de mercado (banca colombiana). 

La decisión más importante a tomar en la reu estratégica es **Camino A vs B vs C**, porque define qué inversiones son críticas y cuáles negociables.

---
