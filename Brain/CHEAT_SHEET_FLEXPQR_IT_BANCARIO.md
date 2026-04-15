# 🎯 Cheat Sheet FlexPQR para conversaciones con IT bancario

> **Propósito**: documento de referencia rápida (6 páginas, denso) 
> para llevar a reuniones con áreas de IT, seguridad y compliance 
> de bancos colombianos. Pensado para consultar en vivo durante 
> reuniones, no para leer linealmente.
>
> **Audiencia**: Nico (founder técnico) en conversaciones con CISO, 
> arquitecto de seguridad, jefe de infraestructura, o equivalente 
> de bancos clientes potenciales.
>
> **Estado**: ESQUELETO. Llenar en sesión dedicada de ~2 horas.
> Última actualización: 14-abril-2026

---

## 📄 Página 1 — Arquitectura en una vista

> **Llenar**: diagrama de arquitectura en ASCII art o referencia a 
> imagen. Componentes principales con sus tecnologías. Flujo de un 
> request de usuario end-to-end en 5 pasos.

**Stack actual**:
- Frontend: [llenar — Next.js 14, React, Tailwind, hospedado en X]
- Backend: [llenar — FastAPI Python 3.11, async, hospedado en X]
- Base de datos: [llenar — PostgreSQL 15 con RLS]
- Cache: [llenar — Redis 7]
- Object storage: [llenar — MinIO con bucket pqrs-vault]
- Message broker: [llenar — Kafka + Zookeeper para procesamiento async]
- AI: [llenar — Anthropic Claude API para clasificación + generación]
- Email: [llenar — Zoho Mail con OAuth]
- Reverse proxy: [llenar — Nginx con TLS termination]

**Flujo de un email entrante** (5 pasos):
1. [llenar]
2. [llenar]
3. [llenar]
4. [llenar]
5. [llenar]

---

## 📄 Página 2 — Las 10 preguntas más probables y sus respuestas

> **Llenar**: una respuesta de 2-3 párrafos para cada pregunta.

### P1: ¿Cómo aíslan los datos de un cliente de los de otro? (multitenancy)
[llenar respuesta corta + razonamiento técnico]

### P2: ¿Cómo manejan la autenticación y autorización?
[llenar — JWT + bcrypt + RBAC + RLS]

### P3: ¿Qué hacen con los datos al terminar un contrato? (exit plan)
[llenar — referencia al exit plan en BANCO_POPULAR_ANALISIS_SEGURIDAD.md]

### P4: ¿Tienen ISO 27001 / SOC 2?
[llenar — respuesta honesta: no hoy, plan formal en roadmap]

### P5: ¿Quién puede acceder al servidor donde corren nuestros datos?
[llenar — bus factor + plan de mitigación con segundo operador]

### P6: ¿Cómo cifran los datos? (en tránsito y en reposo)
[llenar — TLS 1.2/1.3 + KMS + HSTS]

### P7: ¿Qué pasa si su sistema se cae?
[llenar — RTO/RPO + plan de continuidad + DR site]

### P8: ¿Cómo detectan intrusiones o accesos no autorizados?
[llenar — CloudTrail + GuardDuty + audit log + alertamiento]

### P9: ¿Cómo gestionan vulnerabilidades?
[llenar — Dependabot + Trivy + pentesting anual]

### P10: ¿Tienen WAF? ¿Qué protecciones a nivel red?
[llenar — Security Group + WAF en roadmap]

---

## 📄 Página 3 — Justificaciones técnicas clave (decisiones de diseño)

> **Llenar**: por cada decisión técnica importante, dar el "por qué" 
> defendible.

### ¿Por qué PostgreSQL y no otra base de datos?
[llenar]

### ¿Por qué FastAPI y no Django o Spring?
[llenar]

### ¿Por qué Docker Compose y no Kubernetes? (clave)
Ver documento dedicado: `Brain/DECISION_COMPOSE_VS_K8S.md`

### ¿Por qué Anthropic Claude y no GPT-4 o Llama local?
[llenar — privacidad + calidad + soporte enterprise + Colombia]

### ¿Por qué AWS y no Azure / GCP / OnPremise?
[llenar]

### ¿Por qué Row-Level Security en lugar de schemas por tenant?
[llenar — performance + simplicidad + auditabilidad]

### ¿Por qué Kafka para procesamiento async?
[llenar — desacople + escalabilidad futura + audit trail]

---

## 📄 Página 4 — Números importantes

> **Llenar**: SLAs, volúmenes, tiempos. Esta página es la que más 
> impresiona a IT bancarios cuando son números concretos.

### Volumen de operación actual
- Casos procesados: [llenar — N por día/semana/mes]
- Tenants activos: [llenar — N tenants productivos]
- Usuarios activos: [llenar — N usuarios concurrentes pico]
- Adjuntos almacenados: [llenar — 576 a abril-2026, +145 últimos 7 días]
- Volumen total MinIO: [llenar — 399 MB a abril-2026]

### Tiempos de respuesta del sistema
- Latencia mediana del backend: [llenar — Nms]
- Tiempo de clasificación IA por caso: [llenar — Ns]
- Tiempo de generación de respuesta: [llenar — Ns]

### SLAs internos vs regulatorios
- SFC requiere para PQRS financiero: 8 días hábiles
- Ley 1755/2015 para PQRS general: 15 días hábiles
- FlexPQR mediana actual de respuesta: [llenar — Ndías]
- Tutelas: 48 horas (constitucional)
- FlexPQR mediana actual para tutelas: [llenar — Nh]

### Disponibilidad
- Uptime últimos 90 días: [llenar — N%]
- Incidentes mayores últimos 12 meses: [llenar — N]

---

## 📄 Página 5 — Límites claros (qué NO hace FlexPQR)

> **Llenar**: tan importante como saber qué hace el sistema es saber 
> qué NO hace. Evita que un IT piense que FlexPQR cubre algo que no 
> cubre.

### NO procesamos pagos
FlexPQR no es procesador de pagos ni gateway de tarjetas. PCI DSS no aplica.

### NO somos entidad financiera
FlexPQR no es entidad obligada del régimen de Open Finance Colombia. No procesa cuentas, transacciones, ni datos bancarios sensibles del cliente final.

### NO almacenamos credenciales de clientes finales del banco
FlexPQR maneja datos de PQRS (peticiones, quejas, reclamos, sugerencias) y tutelas. No conoce passwords de cuentas bancarias ni tokens de acceso a sistemas core del banco.

### NO somos integradores con core bancario directo
FlexPQR puede integrarse vía APIs estándar (REST, OAuth) pero no se conecta directo a mainframe IBM, AS/400, o sistemas legacy del banco. Si requiere integración profunda, se usa middleware/ESB del banco.

### NO ofrecemos análisis predictivo de fraude
FlexPQR clasifica peticiones por tipología y urgencia. No predice fraude transaccional ni hace AML/KYC.

### NO operamos 24/7 con SLA garantizado hoy
[llenar honestamente con el estado actual y el roadmap a 24/7]

### NO firmamos digitalmente documentos legales con certificados regulados
FlexPQR genera respuestas en PDF firmadas con flujo de doble aprobación interno. Si el banco requiere firma digital con certificado de Banco República o equivalente, se integra con su servicio de firma.

---

## 📄 Página 6 — Roadmap de compliance bancario

> **Llenar**: qué se está trabajando para subir el nivel.

### Próximos 30 días (commited)
- [llenar — quick wins de los 12 identificados en BANCO_POPULAR_ANALISIS_SEGURIDAD.md]

### Próximos 90 días (planificado)
- [llenar — segundo operador, secrets manager, CI/CD completo]

### Próximos 6 meses (planificado)
- [llenar — assessment de seguridad externo, contratos B2B, política de retención formal]

### Próximos 12 meses (estratégico, depende de inversión)
- [llenar — ISO 27001, multi-AZ HA, SIEM completo]

### Pendientes de decisión comercial
- [llenar — Camino A vs B vs C, presupuesto pentesting, presupuesto certificación]

---

## 🎤 Phrases ready to use en reuniones

> **Llenar**: frases pre-armadas en lenguaje bancario para usar en vivo.

- "Estamos en etapa de producto donde priorizamos velocidad de iteración con simplicidad operativa, y tenemos un roadmap formal de compliance que estamos ejecutando en paralelo a las conversaciones comerciales."
- [llenar más frases]

---

**Última actualización**: 14-abril-2026  
**Próxima revisión**: cuando se complete el llenado de placeholders
