# SLA Legal Tracking -- FlexPQR

## Normativa Colombiana

FlexPQR calcula plazos de respuesta basados en la legislacion colombiana:

| Tipo de Caso | Plazo (Dias Habiles) | Base Legal                              |
|--------------|---------------------|-----------------------------------------|
| TUTELA       | 2                   | Decreto 2591 de 1991                    |
| PETICION     | 15                  | Art. 23 Constitucion, Ley 1755 de 2015  |
| QUEJA        | 15                  | Circular Basica Juridica SFC            |
| RECLAMO      | 15                  | Circular Basica Juridica SFC            |
| SOLICITUD    | 10                  | Ley 1755 de 2015                        |
| CONSULTA     | 30                  | Ley 1755 de 2015                        |
| FELICITACION | 5                   | Buena practica                          |

## Calculo de Fecha de Vencimiento

### Trigger SQL: fn_set_fecha_vencimiento
- Se ejecuta automaticamente al INSERT en pqrs_casos
- Consulta la tabla `festivos_colombia` para excluir dias no habiles
- Excluye sabados y domingos
- Calcula la fecha_vencimiento sumando los dias habiles correspondientes al tipo_caso

### Tabla festivos_colombia
```sql
CREATE TABLE festivos_colombia (
    fecha DATE PRIMARY KEY,
    descripcion VARCHAR(100)
);
```
Se precarga con festivos del ano en curso.

## Semaforo SLA

Cada caso tiene un campo `semaforo_sla` con valores:

| Color    | Significado                                     |
|----------|--------------------------------------------------|
| VERDE    | Dentro del plazo                                 |
| AMARILLO | Proximo a vencer (< 2 dias habiles restantes)    |
| ROJO     | Vencido                                          |

## Metricas Relacionadas

El endpoint `GET /api/v2/stats/dashboard` retorna:
- `vencidos` -- Cantidad de casos donde `fecha_vencimiento < NOW()` y estado != CERRADO
- `casos_criticos` -- Casos con prioridad ALTA o CRITICA

## Acuse de Recibo

Cuando un caso se radica, se envia automaticamente un email HTML al ciudadano con:
- Numero de radicado
- Tipo de caso
- Fecha limite de respuesta
- Badge de color segun el tipo

Implementado en `ZohoServiceV2.send_acuse_recibo()`.
