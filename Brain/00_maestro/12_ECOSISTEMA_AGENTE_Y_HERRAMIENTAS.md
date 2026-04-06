---
tags:
  - brain/maestro
---

# Ecosistema de Agentes y Herramientas -- FlexPQR

## Skills Disponibles

Los Skills son instrucciones especializadas que el agente IA lee antes de codificar componentes criticos. Ubicados en `.agents/skills/` y `Skill/`.

### 1. event-driven-architect
- **Proposito:** Disenar productores, topicos, particiones y consumidores en Kafka tolerantes a fallos
- **Uso:** Workers que consumen de Kafka con reintentos automaticos y DLQ
- **Principios clave:** Desacoplamiento absoluto, idempotencia, event sourcing
- **Anti-patrones:** Sync loops, perder eventos, offsets manuales en desorden

### 2. postgres-rls-expert
- **Proposito:** Configurar RLS para multitenancy inquebrantable a nivel motor
- **Uso:** Migraciones, particionamiento, indices parciales
- **Principios clave:** Aislamiento DB-level, set_config por sesion, indices parciales
- **Anti-patrones:** Tenanting en backend, indices redundantes, OLAP en OLTP

### 3. kubernetes-cloud-engineer
- **Proposito:** Despliegue en K8s con KEDA autoscaling
- **Uso:** Manifiestos YAML, autoscalado por lag de Kafka, FinOps
- **Principios clave:** Dockerfiles slim, liveness/readiness, KEDA ScaledObject
- **Anti-patrones:** StatefulSets innecesarios, falta de graceful shutdown

### 4. react-performance-master
- **Proposito:** SSE, virtualizacion de listas, rendimiento en Next.js
- **Uso:** Dashboard con 60 FPS, listas masivas, streaming en vivo
- **Principios clave:** Virtualizacion DOM, TanStack Query, SSE, Skeleton/Suspense
- **Anti-patrones:** Context API para data fetching, variables globales JWT, Array.map de 50k divs

## MCPs Configurados

Archivo: `.mcp.json` en raiz del proyecto.

| MCP               | Tipo    | Uso                                          |
|--------------------|---------|----------------------------------------------|
| mcp-postgres-v2    | npx     | Leer esquema, EXPLAIN ANALYZE, validar RLS   |
| mcp-filesystem     | npx     | Acceso a archivos del proyecto                |
| mcp-obsidian       | npx     | Memoria persistente del agente                |
| mcp-context7       | npx     | Documentacion actualizada de librerias        |
| mcp-github         | npx     | Issues, PRs, code search en GitHub            |

## MCPs Planificados (No Implementados)

| MCP               | Proposito                                           |
|--------------------|-----------------------------------------------------|
| mcp-kafka-monitor  | Leer estado de colas, inyectar eventos de prueba     |
| mcp-redis          | Verificar rate limiting, cache de auth               |
| mcp-kubernetes     | Logs de contenedores, restart de workers             |
| mcp-stripe         | Billing sandbox, facturas, webhooks de pagos         |
