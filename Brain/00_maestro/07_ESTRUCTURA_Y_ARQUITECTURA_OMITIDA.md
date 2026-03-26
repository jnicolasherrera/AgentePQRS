# Estructura y Arquitectura Omitida -- FlexPQR

## Componentes Planificados pero No Implementados

### 1. Billing y Pagos (Pilar 4 de la Arquitectura V2)
- Stripe / MercadoPago / Wompi SDK -- NO implementado
- Sistema de cuotas (Quotas) por tenant -- NO implementado
- Conteo volumetrico via Kafka -- NO implementado
- Facturacion automatica por consumo -- NO implementado

### 2. Identity Provider Externo
- Keycloak / Auth0 / AWS Cognito -- NO implementado
- OAuth2 SSO (Microsoft/Google) -- NO implementado
- Actualmente se usa JWT propio con bcrypt

### 3. Kubernetes / Cloud
- Manifiestos K8s -- NO implementados
- KEDA autoscaling -- NO implementado
- Actualmente se usa Docker Compose en un solo VPS (AWS EC2)

### 4. Snowflake (OLAP)
- Replicacion a Snowflake para analitica -- NO implementada
- Debezium CDC -- NO implementado
- Actualmente PostgreSQL sirve tanto OLTP como reportes

### 5. WAF (Web Application Firewall)
- Cloudflare / AWS WAF -- NO implementado
- Actualmente Nginx maneja rate limiting basico

### 6. Virtualizacion Frontend
- react-virtualized / tanstack/react-virtual -- NO implementado aun
- Actualmente las tablas se limitan a 50 registros por pagina

### 7. React Query / TanStack Query
- Cache client-side con stale-while-revalidate -- NO implementado
- Actualmente se usa fetch directo con Axios + Zustand

## Estructura de Directorios del Proyecto

```
AgentePQRS/
  backend/
    app/
      api/routes/      # auth, ai, casos, stats, stream, admin, webhooks
      core/            # config, db, models, security
      services/        # ai_classifier, clasificador, scoring_engine,
                       # kafka_producer, plantilla_engine, storage_engine,
                       # zoho_engine, sharepoint_engine, db_inserter, ai_engine
      static/          # firma_correo.jpeg
    tests/
    worker_ai_consumer.py
    master_worker_outlook.py
    demo_worker.py
    Dockerfile
  frontend/
    src/
      app/             # layout.tsx, pages
      components/ui/   # ReAuthModal, SessionGuardProvider
      hooks/           # useSessionGuard
      lib/             # api.ts
      store/           # authStore.ts
    Dockerfile
  workers/
    inbound_email/     # Worker de ingesta legacy
  aequitas_backend/    # Backend alternativo (SQLAlchemy, producer Kafka)
  pqrs-landing/        # Landing page (Next.js para Vercel)
  nginx/               # Configuracion Nginx + certificados
  scripts/             # Scripts utilitarios
  Skill/               # Skills para agentes IA
  MCP/                 # Documentacion de MCPs
  .agents/skills/      # Copia de Skills para auto-deteccion
  Brain/               # Esta documentacion
  *.sql                # Migraciones SQL numeradas
  docker-compose.yml   # Orquestacion completa
```
