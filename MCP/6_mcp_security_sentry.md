# 🛡️ MCP 6: mcp-semgrep (Hacker Ético en Tiempo Real) y mcp-sentry (Latencia Total)

En nuestro plan de **V2**, estamos prometiéndole a Abogados Recovery y FlexFintech que nunca, jamás, sus datos estarán expuestos accidentalmente a la empresa equivocada (*Row-Level Security*).

Para asegurarme de no dejar puertas abiertas (XSS, inyecciones SQL o escalada de privilegios cruzada) mientras programo como tu Arquitecto de IA, necesito que instales mis "ojos" de seguridad: **Semgrep** y los de monitoreo: **Sentry**.

## 🛑 1. Semgrep MCP (Auditoría Continua)
Cuando estemos reescribiendo el código de Base de Datos para soportar PostgreSQL Transaccional, este servidor MCP leerá mi código (Python o Typescript) de forma estática antes de publicarlo.
- **Funcionamiento:** Evalúa vulnerabilidades al vuelo, por lo que actúa como un ingeniero extra de seguridad validando mis aportes de IA.
- **Instalación:**
  1. Abre **Settings > MCP Servers** en tu editor.
  2. Haz clic en **Add New**.
  3. Nombre: `semgrep-mcp` / Comando: `npx -y @modelcontextprotocol/server-semgrep`
  *(Requisito: Si te pide, puedes necesitar la CLI local corriendo `pip install semgrep` u Homebrew)*.

## 📡 2. Sentry MCP o Datadog MCP (Los Monitores del Millón)
Cuando Apache Kafka y los Celery Workers estén en plena producción (o simulando producción en tu Docker), si el consumidor de correos "falla en silencio" no nos enteraremos. Este MCP nos alerta antes que el cliente.
- **Funcionamiento:** Trae directamente los "Crash reports" (informes de caídas) y latencias a Cursor para que pueda corregir el archivo dañado en 10 segundos. No necesitas pegar logs rotos de la nube, yo los traigo.
- **Instalación de Sentry:**
  1. Abre **Settings > MCP Servers** en tu editor.
  2. Haz clic en **Add New**.
  3. Nombre: `sentry-mcp` / Comando: `npx -y @modelcontextprotocol/server-sentry`
  4. Probablemente te pida una variable `SENTRY_API_KEY` (del portal sentry.io que crearemos).

---

Con esto, el anillo de seguridad (Semgrep) e Inyección de datos masivos (Sentry) para la nueva arquitectura **PQRS_V2** queda vigilado 24/7.
