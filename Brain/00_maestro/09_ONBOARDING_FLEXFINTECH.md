# Onboarding FlexFintech -- FlexPQR

## Tenants Actuales

### 1. FlexFintech (Tenant Principal)
- **UUID:** a1b2c3d4-e5f6-7890-1234-56789abcdef0
- **Dominio:** flexfintech.com
- **Buzon Outlook:** clientes@flexfintech.com
- **Uso:** Gestion de PQRS de clientes fintech

### 2. Abogados Recovery of Credits S.A.S.
- **UUID:** effca814-b0b5-4329-96be-186c0333ad4b
- **Dominio:** abogadosrecovery.com
- **Proveedor email:** Zoho Mail
- **Uso:** Cobranza legal, gestion de suplantaciones, paz y salvos
- **Plantillas especializadas:** DEBITOS_AUTOMATICOS, PAZ_Y_SALVO_RAPICREDIT, SUPLANTACION_RAPICREDIT, ELIMINACION_CENTRALES, PAZ_Y_SALVO_FINDORSE

## Proceso de Alta de un Nuevo Tenant

1. Insertar registro en `clientes_tenant` (nombre, dominio)
2. Crear usuario admin: `INSERT INTO usuarios` con `rol='admin'` y `cliente_id` del tenant
3. Configurar buzon: `INSERT INTO config_buzones` con credenciales del proveedor email
4. (Opcional) Cargar plantillas en `plantillas_respuesta` para el tenant
5. El worker de polling detectara automaticamente el nuevo buzon activo

## Configuracion de Buzones por Proveedor

### Outlook (Microsoft Graph)
- Requiere: Azure App Registration (client_id, client_secret, tenant_id)
- El campo `azure_folder_id` apunta al folder de Inbox en el buzon
- El `master_worker_outlook.py` itera sobre buzones activos con proveedor='OUTLOOK'

### Zoho Mail
- Requiere: OAuth2 App (client_id, client_secret) + refresh_token + account_id
- Se configura en `config_buzones` con proveedor='ZOHO'
- El campo `zoho_refresh_token` se renueva automaticamente via OAuth2

## Plazos Legales por Tipo de Caso

| Tipo         | Dias Habiles | Prioridad |
|--------------|-------------|-----------|
| TUTELA       | 2           | CRITICA   |
| QUEJA        | 15          | ALTA      |
| RECLAMO      | 15          | ALTA      |
| PETICION     | 15          | MEDIA     |
| SOLICITUD    | 10          | MEDIA     |
| CONSULTA     | 30          | BAJA      |
| FELICITACION | 5           | BAJA      |


## Referencias

- [[03_ONBOARDING_INTEGRACIONES]]
- [[08_MIGRACION_RECOVERY_ZOHO]]
- [[service_zoho_engine]]
