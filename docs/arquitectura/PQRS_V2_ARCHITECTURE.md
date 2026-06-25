# Arquitectura PQR_V2: Escalabilidad a Nivel Enterprise (>1 Millón de PQRs/mes)

El objetivo de esta versión 2.0 es rediseñar y fortalecer el sistema actual de `flex-colombia-pqr` para manejar un tráfico masivo sin latencia, caídas, o embotellamientos en la base de datos o en el motor de clasificación de Inteligencia Artificial.

Con el objetivo en mente de escalar de forma limpia, separada en tenants, y preparada para el ecosistema Cloud (AWS/Azure), presento aquí los **7 Pilares Fundamentales** sobre los que se debe construir `PQRS_V2`.

---

## 🏗️ 1. Backend (El Motor Transaccional & Ingesta)
Actualmente tenemos un monolito en FastAPI (Sincrónico/Mixto).
Para recibir hasta 1.000.000 de emails/tickets al mes (aprox. 33.000 al día), necesitamos un modelo **Asíncrono Basado en Eventos (Event-Driven Architecture)**.

- **Microservicios o Monolito Modular:** Separar el "Servicio de Ingesta de Correos/API" del "Servicio de Clasificación" y del "Servicio de Front (Vistas/Dashboard)".
- **Message Broker (Cola de Mensajes):** Cuando un correo de Zoho o Outlook entra, el backend transaccional no lo procesa ni guarda el adjunto. Simplemente lo lanza a **Apache Kafka**, **RabbitMQ** o **AWS SQS**.
- **Workers Altamente Concurrentes:** Instancias separadas (Celery Workers o servicios Go/Rust) toman los mensajes de Kafka y en *background* y en paralelo: 1) Clasifican la PQR con IA, 2) Guardan el archivo en MinIO/SharePoint, 3) Inserta en la Base de Datos. Si hay pico de 5,000 correos a las 8 AM, el sistema no se cae, simplemente encola y despacha a máxima velocidad celular.

## 💾 2. Database (Optimización y Persistencia de la Verdad)
Snowflake es excelente para analítica y data warehousing (OLAP), pero para un volumen transaccional de 1M inserciones y actualizaciones al mes, la carga puede ser costosa o lenta (alta latencia transaccional).

- **OLTP vs OLAP:**
  - **Transaccional (Operativa):** Pasar toda la parte operativa pura a **PostgreSQL (Aurora DB o Cloud SQL)**. Las inserciones concurrentes de casos, el control de Auth de usuarios, el estado Kanban (`ABIERTO`, `CERRADO`) vivirán aquí con particionamiento por `CLIENTE_ID` (Separación física de tenants).
  - **Analítica (Reportes):** Snowflake seguirá activo operando como Data Warehouse. PostgreSQL replicará asíncronamente (vía `Debezium` o tareas ETL nocturnas) la metadata en Snowflake. Los Dashboards de los clientes leen y extraen todo únicamente desde Snowflake, sin competir por los recursos del PostgreSQL donde entran los casos en crudo.
- **Caché Distribuida:** Redis Cluster fuerte para sesiones, rates limiting al API, y cachear métricas recurrentes que toman tiempo de procesar.

## 💻 3. Frontend (Rendimiento del Cliente)
- Continúa la estructura React (Next.js), pero implementando un patrón de **SSG (Static Site Generation)** para las páginas compartidas y un riguroso **Client-Side Fetching con React Query (SWR / Tanstack)** para los micro-componentes.
- **Virtualización:** Si el cliente tiene un listado histórico de 100,000 PQRs en su tabla de la web, debe renderizarse de modo virtual (ej. `react-virtualized`) cargando en bloques en el DOM sin recargar la RAM de su navegador.
- **Conexiones Reales (WebSockets/SSE):** En vez de recargar la página para ver si un nuevo ticket entró, el frontend usará `Server-Sent Events` para inyectar en directo la PQR clasificada por la IA a la pantalla.

## 💳 4. Pagos y Cobranzas (Payments)
Dado que gestionarán altísimos volúmenes, la monetización será crucial.
- Implementación de la SDK de **Stripe** o pasarelas locales (MercadoPago/Wompi) encapsulada en el servicio `PaymentService`.
- **Billing Automatizado por Consumo:** Un sistema de cuotas (Quotas) atado al `CLIENTE_ID`. Ej. "Plan Avanzado = límite 100k pqrs/mes". Kafka lleva una cuenta volumétrica y cuando sobrepase el nivel de tier, lanza una cuenta por Cobrar (Invoice) en la plataforma del usuario usando Stripe Registrations. Se guardará un log transaccional inmutable.

## 🛡️ 5. Seguridad & Multitenancy Estricto
Con esta escala de información, los estándares deben ser bancarios.
- **Identity Provider (IdP):** Separar la lógica actual de Auth en favor de **Keycloak**, Auth0 o AWS Cognito en donde el OAuth2 (SSO para Microsoft / Google) venga delegado de base.
- **Multitenancy Basado en Row-Level Security (RLS) en PostgreSQL:** Cualquier query hacia la base de datos se forzará al nivel del motor de PostgreSQL usando el `CLIENTE_ID` logueado. Es imposible que un error de Backend cruce información entre Abogados Recovery y FlexFintech.
- Encriptación: KMS (Key Management Systems) para las cadenas de conexión a base de datos.
- **WAF (Web Application Firewall):** Protección en la periferia como Cloudflare o AWS WAF para bloquear fuerza bruta (DDos) al login endpoints.

## 🚀 6. Infraestructura y Escalabilidad (Cloud)
- **Kubernetes (EKS / AKS):** Despliegue empaquetado 100% en contenedores. KEDA medirá el largo de la cola de Kafka; si entran miles de PQRs, los pods de trabajadores (Workers) se clonarán autoescalando un 300% para solventarlo, y luego de procesar, volverán a apagar para ahorrar dinero en Azure/AWS.
- **Storage Infinito:** Migración de S3-protocol en nube (Amazon S3 o Azure Blob Storage multi-zonal). El servicio actual `StorageService` se acoplará pero el Storage Backend se convertirá en un hub.

## 📡 7. IA y Automatización (Inteligencia del Proceso)
- Las respuestas (Etapa 2) involucrarán Modelos de Lenguaje Grandes (LLMs). En vez de que cada API call golpee OpenAI/Gemini directamente, usaremos un modelo de streaming asíncrono.
- La PQR ingresada por Kafka pasa el texto completo por el módulo RAG (Generación Aumentada por Recuperación). Busca la jurisprudencia o respuesta predeterminada y lanza el texto sugerido al Front.
- Todo esto monitoreado y registrado para auditoría.

---

### Siguientes Pasos (Ejecución):
Nuestra meta inmediata es **instanciar desde cero este ecosistema en V2**. Mantendremos el conocimiento del negocio pero separaremos las capas.
1. Instalar la nueva arquitectura de base de datos PostgreSQL y Kafka con Docker local para pruebas.
2. Iniciar el API de nueva generación (`backend_v2`) modular que consuma usando colas en vez del proceso bloqueante en for/loop que se usaba antes para traer el correo.
3. Conectar y testear carga masiva.
4. **Desarrollar Landing Page Comercial (PQRS_LANDING):** Un sitio público independiente y de estética "Premium/Glassmorphism" con animaciones dinámicas, que oficie de puerta de entrada e incluya el botón Login hacia esta plataforma V2. 
   - *Herramientas a utilizar:* **Google Stitch** (IA de Text-to-UI) para maquetación rápida y espectacular, exportado en conjunto con **Magic UI MCP** y **Figma MCP** para inyectar componentes listos para producción (vibrantes, modo oscuro y reactivos) directamente desde el chat del editor.

---

### 📜 Historial de Implementación Relevante (V2 Integration):

#### **Fase 1: Motor de Ingesta Inteligente (Completado - Feb 25, 2026)**
- **Integración del Clasificador V1**: Se migró la lógica de RegEx y palabras clave de la versión 1.0 a un nuevo servicio de micro-clasificación asíncrona.
- **Worker de Outlook Optimizado**: Se desplegó el primer microservicio `worker_v2` especializado en Microsoft Graph que inyecta casos clasificados directamente al Dashboard.
- **SLA Legal Colombiano**: Implementación de cálculo de vencimientos por días hábiles usando `pandas` y reglas de negocio específicas por tipo de PQR (Tutelas = 2 días hábiles).
- **Notificaciones SSE Premium**: Conexión de `redis_v2` con el Dashboard para streaming de casos críticos en tiempo real.
