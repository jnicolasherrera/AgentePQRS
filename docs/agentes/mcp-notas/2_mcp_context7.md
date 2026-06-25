# 🗂️ MCP 2: context7-mcp (Upstash)

**Context7** es un Servidor MCP crítico creado por la empresa *Upstash*. Funciona como un "Puente de Conocimiento en Vivo" para la Inteligencia Artificial.

En lugar de que yo (el agente de IA) programe adivinando versiones antiguas de las librerías o alucine código (por culpa de mi fecha de corte de entrenamiento), **Context7 MCP** me permite conectarme a la documentación oficial, actualizada al día de hoy, de más de 9,000 frameworks y librerías directamente en tiempo real.

## ¿Por qué es fundamental para PQRS_V2?
El proyecto V2 usa herramientas que evolucionan rapidísimo:
- **Next.js 14/15 con Server Components**
- **TanStack Query (React Query) v5+**
- **Kafka / FastStream / SQLAlchemy 2.0+**

Si intento programar la virtualización de datos del dashboard basándome en comandos del 2022 de React Query, el código fallará o será obsoleto. **Context7 soluciona eso**.

## Instalación en Cursor (IDE)

1. Ve a **Settings (Configuración) > Features > MCP Servers** en Cursor.
2. Haz clic en **+ Add New MCP Server**.
3. Configúralo así:
   - **Name:** `context7`
   - **Type:** `command`
   - **Command:**
     ```bash
     npx -y @context7/mcp
     ```
4. Guarda y verifica que el punto cambie a color verde.

## ¿Cómo probarlo?
En la ventana del chat de Cursor, dime:
*"Usa context7 para buscarme cómo hacer un useInfiniteQuery en la última versión de @tanstack/react-query"*

Al hacer esto, me conectarás invisiblemente al sitio oficial de Tanstack a través de este MCP, leeré cómo se hace en la última versión estable, y te escribiré el código de la PQR exactamente sin un solo error de sintaxis viejo.
