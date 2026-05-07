# 🏗️ Decisión arquitectónica: Docker Compose vs Kubernetes

> **Estado**: DECIDIDO — Compose hoy, Kubernetes managed para Camino A
> **Fecha de decisión**: 14-abril-2026
> **Decisor**: Nico Herrera (tech lead) con análisis estratégico
> **Próxima revisión**: cuando se firme primer contrato Camino A o cuando se contrate segundo operador

---

## 🎯 La regla popular y por qué es matizada

Existe una recomendación común en círculos de ingeniería senior: *"nunca usar Docker Compose en producción, siempre Kubernetes"*. Esta regla **es técnicamente correcta en cierto contexto y técnicamente incorrecta en otro**. Este documento explica por qué FlexPQR usa Compose hoy y por qué planeamos migrar a Kubernetes managed (EKS o GKE) cuando avancemos al Camino A (SaaS multitenant certificado para banca).

---

## ✅ Argumentos a favor de Kubernetes (cuándo es la opción correcta)

1. **Auto-healing real multi-nodo**: si un container muere, K8s lo reinicia automáticamente en otro nodo. Compose solo restart en el mismo host.
2. **Scaling horizontal sin drama**: K8s corre N réplicas con un comando. Compose corre 1 container por servicio por default.
3. **Rolling updates sin downtime**: K8s hace updates gradual con health checks. Compose hace recreate con segundos de downtime.
4. **Secrets management integrado**: K8s tiene `Secret` como recurso primitivo con RBAC. Compose tiene env vars en YAML.
5. **Multi-nodo nativo**: K8s corre en N máquinas. Compose corre en 1 sola.
6. **Compliance bancaria lo prefiere**: varios frameworks (NIST, PCI) asumen orquestadores enterprise.
7. **Service mesh, observabilidad, network policies**: ecosistema maduro para sistemas distribuidos.

**Conclusión**: K8s es la opción correcta cuando hay tráfico alto, equipo con experiencia K8s, múltiples servicios que necesitan HA, y compliance que lo exige.

---

## ✅ Argumentos a favor de Compose (cuándo es la opción correcta)

1. **Costo operativo bajo**: no requiere control plane, helm charts, manifests, pipelines complejos.
2. **Velocidad de desarrollo alta**: deploy = `docker compose up -d --no-deps <servicio>` en segundos.
3. **Curva de aprendizaje plana**: cualquier desarrollador con Docker básico opera Compose.
4. **Suficiente para tráfico bajo a moderado**: una sola máquina maneja N requests/segundo de un SaaS B2B chico.
5. **Menos superficie de ataque**: K8s tiene su propio CVE list, misconfigs comunes (RBAC mal, etcd sin encrypt, NetworkPolicies flojas).
6. **Bus factor menor**: K8s requiere conocimiento especializado. Compose lo opera cualquier dev mid-level.
7. **Empresas exitosas corren Compose en producción**: muchos SaaS early stage, Basecamp, etc.

**Conclusión**: Compose es la opción correcta cuando hay tráfico bajo, equipo chico, máquina única, prioridad en velocidad de iteración, y compliance no lo exige todavía.

---

## 🎯 Aplicación al contexto actual de FlexPQR

### Estado actual de FlexPQR (abril-2026)
- **1 máquina EC2 t3.large** en sa-east-1
- **1 desarrollador/operador** (Nico — bus factor 1)
- **Tráfico bajo**: N requests por minuto (no segundo), pico horario laboral colombiano
- **2 tenants productivos**: FlexFintech + Abogados Recovery
- **Pipeline comercial bancario en etapa de evaluación**, sin contrato firmado todavía
- **Sin requisitos formales de HA** firmados con clientes

### Análisis aplicado
- Compose **es suficiente** para la escala actual
- Compose **es operable** con confianza por el equipo actual
- Compose **no impide crecer**: cuando llegue el momento, la migración es proyecto dedicado, no rewrite
- Kubernetes **agregaría complejidad sin resolver problema actual**
- Kubernetes **agravaría el bus factor** (Nico tendría que aprender + operar K8s solo)

---

## 📅 Trigger para migración a Kubernetes

La migración a Kubernetes managed (EKS o GKE) se justifica cuando se cumple **al menos uno** de estos triggers:

1. **Contrato bancario firmado en Camino A** (SaaS certificado) que exija HA multi-AZ con SLA garantizado
2. **Crecimiento de tráfico** que sature una máquina (>50% CPU sostenido + >70% memoria)
3. **Crecimiento de equipo** a 3+ desarrolladores con al menos uno con experiencia K8s
4. **Requisito formal de compliance** (auditor SOC 2 o ISO 27001 que exige orquestador enterprise)
5. **Tráfico multi-región** (clientes en países distintos que exigen latencia local)

Hoy (abril-2026) **ninguno de estos triggers está activo**. Por eso Compose sigue siendo la opción correcta.

---

## 🗣️ Respuesta lista para IT bancario

Cuando un IT de banco pregunte *"¿por qué usan Docker Compose y no Kubernetes?"*, la respuesta articulada es:

> *"FlexPQR está en una etapa de producto donde priorizamos velocidad de iteración y simplicidad operativa. Docker Compose es suficiente para la escala actual del negocio y la operamos con confianza. En nuestro roadmap de compliance bancario — que forma parte de la conversación con ustedes — planeamos migrar a una arquitectura Kubernetes managed (EKS o GKE) cuando pasemos al modelo de SaaS multitenant certificado. Esa migración está pensada como proyecto dedicado de 3-4 meses una vez definida la hoja de ruta con el primer cliente bancario."*

Esta respuesta es **honesta, técnicamente defendible, y demuestra madurez de pensamiento estratégico** sin ser defensiva ni evasiva.

---

## 🚫 Anti-patrones que NO aplicar

### "Migrar a K8s ya por si acaso"
**No.** Migrar antes de necesitarlo agrega complejidad sin valor. Aumenta superficie de ataque, agrava bus factor, ralentiza desarrollo.

### "Quedarse en Compose para siempre"
**No.** Cuando los triggers se activen, hay que migrar. Quedarse en Compose con HA bancaria exigida es deuda técnica peligrosa.

### "Usar K8s sin equipo entrenado"
**No.** K8s mal configurado es peor que Compose bien configurado. Si se migra, hay que tener al menos 1 persona con experiencia K8s en el equipo o consultor especializado liderando.

---

## 📚 Referencias y lecturas relacionadas

- Punto 3 de `BANCO_POPULAR_ANALISIS_SEGURIDAD.md` — Arquitectura cloud aceptable para banca
- Punto 10 de `BANCO_POPULAR_ANALISIS_SEGURIDAD.md` — SDLC + bus factor (cruzado con esta decisión)
- Documentación oficial Docker Compose: https://docs.docker.com/compose/
- AWS EKS Best Practices Guide: https://aws.github.io/aws-eks-best-practices/

---

**Próxima revisión obligatoria**: cuando se firme primer contrato bancario que exija HA, o cuando se contrate segundo operador, lo que ocurra primero.
