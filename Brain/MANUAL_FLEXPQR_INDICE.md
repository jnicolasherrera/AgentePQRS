# 📚 Manual FlexPQR — Índice maestro

> **Propósito**: documento de comprensión profunda del producto FlexPQR, 
> estructurado en 4 capas, pensado para que Nico (y eventualmente otros) 
> puedan defender el producto con propiedad técnica frente a IT 
> bancario, inversores, o nuevos integrantes del equipo.
>
> **Diferencia con el Cheat Sheet**: el Manual se lee linealmente y 
> construye comprensión. El Cheat Sheet se consulta como referencia rápida.
>
> **Estado**: ÍNDICE. Llenar en 2-3 sesiones futuras de ~2 horas cada una.
> Última actualización: 14-abril-2026

---

## 🎯 Audiencia

- **Primaria**: Nico, para construir y mantener su propia comprensión 
  estructurada del producto
- **Secundaria futura**: segundo desarrollador/operador cuando se 
  contrate (acelerar onboarding)
- **Terciaria**: eventuales partners técnicos o auditores externos

---

## 🗂️ Estructura de 4 capas

### CAPA 1 — El producto en lenguaje de IT bancario (3-5 páginas)

Cómo describir FlexPQR en 3 minutos a alguien que nunca lo vio, usando el lenguaje que un IT bancario espera escuchar.

**Secciones a llenar**:
- 1.1 Definición operativa de FlexPQR
- 1.2 Marco regulatorio que cubre (Ley 1755/2015, Decreto 2591/1991, Ley 1328/2009, SFC)
- 1.3 Tipos de clientes objetivo (financiero, salud, servicios públicos, telcos, legal, gobierno)
- 1.4 Modelo de deployment (SaaS / on-premise / híbrido)
- 1.5 Clientes actuales y casos de uso reales
- 1.6 Pipeline comercial bancario (sin nombres específicos para confidencialidad)
- 1.7 Diferenciadores frente a alternativas (Aranda, Mesa de Ayuda interna, sistemas legacy del banco)

---

### CAPA 2 — Arquitectura defendible (5-8 páginas)

El diagrama de bloques con la justificación de cada pieza. Para cada componente: qué hace, qué alternativas hay, por qué se eligió esta.

**Secciones a llenar**:
- 2.1 Diagrama de arquitectura completo (componentes + flujos de datos)
- 2.2 Frontend: Next.js — qué hace, alternativas, por qué se eligió
- 2.3 Backend: FastAPI — qué hace, alternativas, por qué se eligió
- 2.4 Base de datos: PostgreSQL 15 con RLS — multitenancy explicado
- 2.5 Cache: Redis 7 — qué cachea, por qué
- 2.6 Object storage: MinIO con pqrs-vault — adjuntos
- 2.7 Message broker: Kafka — por qué async, qué eventos
- 2.8 AI layer: Anthropic Claude — clasificación + generación + RAG futuro
- 2.9 Email: Zoho Mail con OAuth — entrada y salida
- 2.10 Reverse proxy: Nginx — TLS termination + routing
- 2.11 Decisiones cruzadas: por qué Compose y no K8s (referencia a `DECISION_COMPOSE_VS_K8S.md`)
- 2.12 Topología cloud: AWS sa-east-1 + Security Group + S3 backups
- 2.13 Roadmap arquitectónico: qué cambia en Camino A vs B vs C

---

### CAPA 3 — Respuestas a preguntas de auditoría bancaria (5-8 páginas)

Respuestas largas (1-2 páginas cada una) a las preguntas más sustantivas que hacen los IT de bancos.

**Secciones a llenar**:
- 3.1 ¿Cómo aíslan los datos entre tenants? (RLS + RBAC explicado a fondo)
- 3.2 ¿Cómo manejan secretos y credenciales?
- 3.3 ¿Cuál es su exit plan completo? (procedimiento, plazos, formatos, certificación)
- 3.4 ¿Cómo gestionan el ciclo de vida del software? (SDLC, branches, code review, deploy)
- 3.5 ¿Cómo detectan y responden a incidentes? (alertamiento, runbooks, comunicación al cliente)
- 3.6 ¿Cuál es su plan de continuidad ante desastre? (RTO/RPO, DR site, backups)
- 3.7 ¿Cómo cumplen con Ley 1581/2012 (Habeas Data Colombia)?
- 3.8 ¿Quiénes son sus subprocesadores y dónde están los datos?
- 3.9 ¿Cómo manejan la integración con sistemas del banco?
- 3.10 ¿Cuál es su modelo de pricing y SLA garantizado?

---

### CAPA 4 — Límites claros (2-3 páginas)

Qué NO hace FlexPQR, explicado en detalle para evitar malentendidos.

**Secciones a llenar**:
- 4.1 Lo que SÍ es FlexPQR (positiva)
- 4.2 Lo que NO procesa: pagos, datos bancarios sensibles, AML/KYC
- 4.3 Lo que NO ofrece: análisis predictivo, detección de fraude, integración con core bancario directo
- 4.4 Lo que SÍ se puede integrar bajo acuerdo: APIs Open Finance del banco, sistemas de firma digital del banco, SSO con Azure AD del banco
- 4.5 Roadmap explícito de cosas que HOY no se hacen pero están en plan

---

## 📅 Plan de sesiones futuras

| Sesión | Capas a llenar | Tiempo estimado |
|---|---|---|
| Sesión A | Capa 1 + Capa 2 (las más importantes para conversaciones técnicas) | 2 horas |
| Sesión B | Capa 3 (respuestas largas a auditoría) | 2 horas |
| Sesión C | Capa 4 + revisión integral del Manual completo | 1.5 horas |

**Total**: ~5.5 horas distribuidas en 3 sesiones para tener el Manual completo.

---

**Última actualización**: 14-abril-2026  
**Próxima sesión sugerida**: Sesión A — Capa 1 + Capa 2
