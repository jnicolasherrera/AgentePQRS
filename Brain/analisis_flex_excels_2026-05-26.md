# Análisis Excels FlexFintech (Flex/Consolidado Defcon + Reclamos)

**Fecha:** 2026-05-26
**Archivos analizados:**
- `Flex/Consolidado Defcon.xlsx` (256 KB, 11 hojas)
- `Flex/Consolidado Reclamos.xlsx` (3.3 MB, 20 hojas)

**Estado:** análisis-only, NO se aplicó ningún cambio.

---

## TL;DR — qué hay acá

| Recurso | Volumen | Valor de negocio |
|---|---|---|
| **Plantillas reales de respuesta por tipo/motivo** (hojas `Rtas` + `RTA DC`) | **~50 plantillas** | 🔥 Las 5 plantillas hardcoded de Recovery son nada vs esto. Poblarlas en `plantillas_respuesta` → FlexFintech pasa de 0 a 50 plantillas reales instantáneo. **Mayoría de casos van a matchear plantilla exacta = cero costo LLM, respuesta instantánea.** |
| **Casos históricos resueltos** (`Mails`, `Reclamos`, `Consolidado*`, `Colombia`, `Viejo_CO`) | **~2.900 casos** con cédula + tipo + comentario_interno + gestión | 🔥 Material para alimentar el RAG. Hoy el KB tiene 9 enviados Recovery. Esto sube a ~2900. Cada caso es un (problema, solución) real. |
| **Vocabulario controlado** (`Tipificaciones`, `LISTA`) | 5 supervisores, 10 tipos reclamo, 6 estados, 6 entidades origen, 4 alertas | Taxonomía para enriquecer enums del sistema y el dashboard |
| **Mapeo email → cédula** (todas las hojas operativas) | Miles de pares | Identificar al peticionante por email aunque no mencione cédula en el cuerpo |
| **Metadata operacional** | DIAS_ABIERTO, PLAZO, AGENCIA, ULTIMA_ACT, ALERTA | Métricas SLA + routing avanzado |
| **Procesos de negocio** (`Defcon/Documentación`) | Checklist de docs (contrato, pagaré, autorización datos…) | Convertir en checklist por tipo de caso |

---

## Inventario por hoja

### `Consolidado Reclamos.xlsx`

| Hoja | Filas | Qué tiene | Valor |
|---|---|---|---|
| **Rtas** | 43 | **🌟 PLANTILLAS REALES** con TIPO + MOTIVO + MENSAJE completo (incluso emojis) | ALTO |
| **RTA DC** | 8 | **🌟 PLANTILLAS** para Datacrédito (desconocimiento por entidad: Rappi / FLB / Santander / Bogotá / cartera recuperada / pide info / pide doc) | ALTO |
| **Mails** | ~miles | Log de gestión vía email (DOCUMENTO, NOMBRE, MAIL, TIPO, ESTADO, COMENTARIO INTERNO con la GESTIÓN textual) | ALTO |
| **Reclamos** | 1908 | Histórico operativo Colombia con cédula, tipo, comentario, plazo, fecha, dato_contacto | ALTO |
| **CONSOLIDADO SANTANDER** | 59 | Cerrados Santander con métricas tiempo | MEDIO |
| **CONSOLIDADO BOGOTA** | 30 | Cerrados Bogotá | MEDIO |
| **PAZ Y SALVO** | 671 | Tracking pedidos paz y salvo (FECHA, CEDULA, EMITIDO, ENVIADO, CORREO) | MEDIO (operacional) |
| **Asignación** | 186 | Pedidos de reasignación de agencia | BAJO (operacional) |
| **TPIFICACIONES** | 11 | Vocabulario: supervisor, país, tipo, avance, canal, estado mails, tipo reclamo, cesión | MEDIO |
| INFORME PAULI / Metricas / FOTO MAILS / FOTO RECLAMOS / Info / Casos a mandar rappi / Call Reclamos / FDP aprox / ACT. CR. / 18602930 / Cesion | varios | dashboards y operativos sueltos | BAJO |

### `Consolidado Defcon.xlsx`

| Hoja | Filas | Qué tiene | Valor |
|---|---|---|---|
| **Colombia** | 559 | Histórico Colombia con cédula, periodo, supervisión, entidad_origen, tipo, estado, fechas, comentario, email | ALTO |
| **Viejo_CO** | 344 | Histórico Colombia anterior | ALTO |
| **Reclamos** | 5 | Casos abiertos paz y salvo (CEDULA, NOMBRE, MAIL DE CONTACTO, OPERACIÓN ORIGEN, TIPO, AVANCE, COMENTARIO) | MEDIO |
| **Argentina** | 69 | Histórico AR | MEDIO (no FlexFintech CO) |
| **Uruguay** | 2 | Histórico UY | BAJO |
| **Casos denuncia** | 3 | Suplantaciones pendientes | MEDIO |
| **Tipificaciones** | 6 | Vocabulario: Supervisor, Alerta, Tipo Reclamo, Estado, LVM, Entidad Origen | MEDIO |
| **Documentación** | 10 | Checklist de docs para defcon: contrato, pagaré, autorización datos… | MEDIO |
| **LISTA** | 7 | Taxonomía por país (COLOMBIA: Dcho Petición, Tutela, Insolvencia, Suplantación, Denuncia / ARGENTINA: Defcon, Conciliación / ESTADOS: Cerrado, Proceso) | MEDIO |
| Casos para negociar | 19 | Operativo interno | BAJO |
| Fran | 16 | Dashboard | BAJO |

---

## Las 50 plantillas reales — sample

### `Rtas` (43 plantillas operativas)

| TIPO | MOTIVO | Resumen mensaje |
|---|---|---|
| PAZ Y SALVO | PEDIDO PAZ Y SALVO | "📩 Hola, ¡gracias por contactarte con Flex Fintech! 😊 Para solicitar tu certificado de cancelación…" |
| IDENTIFICACION CLIENTE | PEDIR DOCUMENTO | "Estimado cliente, Para poder asistirle con su consulta, le solicitamos amablemente que nos comparta…" |
| COMPROBANTE | COMPROBANTE RECIBIDO | "Gracias por enviarnos el comprobante de pago. Te confirmamos que lo hemos recibido…" |
| COMPROBANTE | COMPROBANTE SIN DOCUMENTO | variante anterior |
| ATENCION AL CLIENTE | CASO EN REVISIÓN | "Le confirmamos que su caso ya fue asignado…" |
| ATENCION AL CLIENTE | PENDIENTE RTA CLIENTE | recordatorio |
| ATENCION AL CLIENTE | CIERRE NO RTA CLIENTE | cierre por falta de respuesta |
| … 36 más | … | … |

### `RTA DC` (8 plantillas — desconocimiento de deuda por entidad)

| TIPO | Mensaje |
|---|---|
| Pedido de documentación | "POR FAVOR ESCRÍBANOS AL CORREO CLIENTES@FLEXFINTECH.CO…" |
| Desconoce Rappi | "FLEX FINTECH ES EL ACREEDOR DE SU OBLIGACIÓN ORIGEN RAPPI PAY…" |
| Desconoce FLB | idem Falabella |
| Desconoce Santander | idem |
| Desconoce Bogotá | idem |
| Cliente Pide Info | "AGRADECEMOS SU CONTACTO POR FAVOR ESCRÍBANOS AL CORREO…" |
| Cartera Recuperada | "SU OBLIGACIÓN FIGURA COMO CARTERA RECUPERADA, LO QUE SIGNIFICA QUE REGULARIZÓ SU DEUDA…" |

---

## Lo que esto cambia — propuestas concretas

### 🥇 **Tier 1 — IMPACTO INMEDIATO** (cargar mañana mismo)

**P1. Importar las ~50 plantillas a `plantillas_respuesta` (tenant FlexFintech)**
- 1 INSERT por plantilla con `(cliente_id, problematica, cuerpo, contexto, keywords, is_active=TRUE)`.
- Mapear cada (TIPO, MOTIVO) del Excel a un `problematica` slug:
  - `PAZ Y SALVO + PEDIDO PAZ Y SALVO` → `PEDIDO_PAZ_Y_SALVO`
  - `RTA DC + Desconoce Rappi` → `DESCONOCIMIENTO_RAPPI`
  - etc.
- Costo de ejecución: **0** (sin LLM). Tiempo: 30 min (script Python que parsea el Excel + bulk insert).
- **Resultado**: FlexFintech pasa de 100% caso al fallback Claude → mayoría de casos a plantilla exacta + Claude solo para los novedosos.

**P2. Reglas `_DETECTION_RULES` en `plantilla_engine.py`**
- Agregar keywords para cada problematica nueva. Ejemplo:
  ```python
  ("PEDIDO_PAZ_Y_SALVO", ["paz y salvo", "certificado de cancelación", "libre de deuda"], []),
  ("DESCONOCIMIENTO_RAPPI", ["no conozco", "no reconozco", "no es mía"], ["rappi"]),
  ("COMPROBANTE_RECIBIDO", ["adjunto comprobante", "comprobante de pago"], []),
  ```
- Tiempo: 1 hora.
- **Resultado**: detección automática matchea las plantillas correctamente.

**P3. Persistir cédula plana en `pqrs_casos`** (ya planeado para sprint FlexFintech operativo)
- Migración 18 agrega `documento_peticionante VARCHAR(20)` + populate retroactivo extrayendo de body con regex.
- Necesario también para naming de carpetas SharePoint (`{cedula}_{fecha}/`).

### 🥈 **Tier 2 — IMPACTO ALTO** (esta semana)

**P4. Backfill al RAG de los ~2.900 casos históricos como `caso_enviado` virtuales**
- Script que importa cada fila de `Mails`+`Reclamos`+`Colombia`+`Viejo_CO` como un doc al KB:
  - `contenido` = `"TIPO: {tipo_reclamo}\nGESTIÓN: {comentario_interno}\nESTADO FINAL: {estado}"`
  - `problematica` = mapping del tipo.
  - `tipo_caso` = mapping a TUTELA/PETICION/RECLAMO/QUEJA/SOLICITUD.
  - `metadata` = `{cedula, mail, agencia, supervisor, periodo, fuente: "excel-defcon-2026-05-26"}`.
- Costo embeddings Voyage: 2900 × ~80 tokens promedio = 232K tokens = **$0.028** (con tier paid; con free saturaría rate limit — hacer en lotes con sleep).
- **Resultado**: el RAG retrieva no solo las 50 plantillas, sino casos REALES con gestiones REALES → respuestas mucho más afinadas al estilo del operador humano histórico.

**P5. Vocabulario controlado** — taxonomías del Excel a tags/enums del sistema
- Tabla nueva `casos_tags` opcional o `metadata_especifica` JSONB con:
  - `entidad_origen`: Rappi, Falabella, Santander, Bogotá, Credifinanza, FLB.
  - `agencia`: número de agencia (15, 21, 64, 108, 111, 114, 115, 121…).
  - `supervisor_propuesto`: Micaela / Ana Paula / Gabriel (round-robin con preferencia por carga del Excel).
  - `alerta`: NORMAL / ATENCIÓN / CRÍTICO (sobre nuestro `nivel_prioridad` o como override).
- Dashboard puede filtrar por estos tags.

**P6. Mapeo email → cédula histórico**
- Tabla auxiliar `historico_email_cedula(email, cedula, ultimo_visto)` poblada del Excel.
- Cuando llega un caso nuevo: si el sender está en la tabla → autocompleta `documento_peticionante` aunque el body no mencione cédula.
- Beneficio: SharePoint folder naming `{cedula}_{fecha}` funciona aunque el body sea pobre.

### 🥉 **Tier 3 — IMPACTO MEDIO** (próximo sprint)

**P7. Routing por agencia/supervisor según preferencia histórica**
- `master_worker_outlook.py:272` round-robin actual ignora agencia/entidad.
- Ej: si el caso es CRÍTICO + entidad SANTANDER → preferir Micaela (porque históricamente lleva esos).
- Análisis del Excel: ver qué supervisores llevan qué entidades.

**P8. Métricas estilo Paola**
- Hojas `INFORME PAULI`, `Info`, `Metricas` dan pistas del dashboard que esperan:
  - Estados de atención por periodo.
  - Tiempo de atención promedio.
  - Gestión de mails vs gestión de reclamos.
- Probable que el otro agente que está laburando métricas/frontend ya esté apuntando en esa dirección.

**P9. Checklist de docs por tipo de caso** (`Defcon/Documentación`)
- 1. Contrato de vinculación del deudor
- 2. Pagaré suscrito
- 3. Autorización tratamiento datos personales
- … (lista completa al revisar la hoja entera)
- Modelar como checklist UI que los abogados marcan antes de enviar.

### 🛑 **NO HACER** (deprioritizar)

- Hojas de Argentina / Uruguay: no son FlexFintech CO, otra geografía con otra normativa.
- Hojas `Casos para negociar`, `Fran`, `INFORME PAULI` raw: son dashboards/operativos, no datos reutilizables.

---

## Recomendación de ejecución

**Mañana junto al sprint FlexFintech operativo** (override destinatario + SharePoint + cedula plana):
- Sumar **P1 + P2 + P3** del Tier 1. Son 2-3 horas extra al sprint.
- El impacto es brutal: FlexFintech pasa de "0 plantillas, todo a Claude" a "50 plantillas reales, RAG con normativa + casos previos cuando no hay match".

**Esta semana (después del sprint)**:
- **P4** backfill RAG (1 día, requiere payment Voyage activado para no saturar rate limit free).
- **P5** vocabulario controlado (medio día).

**Próximo sprint**:
- **P6, P7, P8, P9** según prioridad de Paola/Mica.

---

## Preguntas que necesitan respuesta del cliente (vos / Mica / Paula)

1. **¿Las plantillas `Rtas` y `RTA DC` están vigentes?** Algunas pueden estar desactualizadas — confirmar antes de cargarlas masivamente.
2. **¿Los ~2900 casos históricos se pueden usar para entrenar el RAG?** Implica que la "gestión" del operador histórico se publica como contexto inspiracional para Claude → confirmar privacidad / legal.
3. **¿El régimen SLA de FlexFintech es FINANCIERO o GENERAL?** (pendiente del análisis anterior). Los plazos SFC (8 días hábiles para QUEJA/RECLAMO) cambian si es financiero.
4. **¿Querés mantener la lógica "Siempre enviar a Fabio" (Defcon/Documentación)?** Si sí, hay que modelar a Fabio en el sistema como destinatario forzado en ciertos casos.
5. **¿Los códigos de agencia (15, 21, 64, 108, 111…) tienen significado de negocio?** ¿Tenemos que mapearlos a nombres legibles para el dashboard?

---

## Anexo — comandos de inspección reproducibles

```bash
# Ver una hoja completa con todas las filas
docker exec pqrs_v2_backend python -c "
import openpyxl
wb = openpyxl.load_workbook('/tmp/reclamos.xlsx', data_only=True, read_only=True)
ws = wb['Rtas']
for row in ws.iter_rows(values_only=True):
    print(row)
"
```
