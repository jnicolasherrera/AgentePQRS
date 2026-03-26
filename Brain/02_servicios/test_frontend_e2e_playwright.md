# Tests: Frontend E2E (Playwright)

## Estado Actual

No hay tests E2E con Playwright implementados actualmente. Este documento describe la estrategia planificada.

## Flujos Criticos a Testear

### 1. Login y Autenticacion
- Login exitoso con credenciales validas
- Login fallido con credenciales invalidas
- Redirect a /login cuando no hay sesion
- Re-autenticacion inline cuando token expira

### 2. Dashboard
- Carga de KPIs correctamente
- Distribucion de estados se renderiza
- Ultimos casos se muestran en tabla
- Filtros de busqueda funcionan

### 3. Detalle de Caso
- Navegacion desde tabla a detalle
- Carga de comentarios y adjuntos
- Edicion de borrador
- Rechazo de borrador

### 4. Aprobacion por Lote
- Seleccion de multiples casos
- Confirmacion de password
- Envio exitoso

### 5. SSE en Tiempo Real
- Nuevos casos aparecen sin recargar
- Filtrado por rol funciona

## Configuracion Sugerida

```bash
# Instalar Playwright
npm init playwright@latest

# Configurar base URL
# playwright.config.ts -> baseURL: 'http://localhost:3002'
```

## Fixtures Necesarios

- Seed de tenant de prueba
- Seed de usuario admin y analista
- Seed de casos de prueba
- Mock de servicios externos (Zoho, Anthropic)
