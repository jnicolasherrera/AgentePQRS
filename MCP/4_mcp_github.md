# 🐙 MCP 4: mcp-github

Para un proyecto Enterprise (V2) manejado por múltiples clientes y con un tráfico de 1 Millón de PQRs, el código no puede vivir solo en discos duros locales. Necesitamos Integración y Despliegue Continuo (CI/CD), control de versiones estricto y revisión de arquitecturas.

El Servidor **GitHub MCP** otorga a tu Inteligencia Artificial la capacidad de leer, interactuar y administrar repositorios de GitHub sin salir de tú chat.

## 🚀 Capacidades de este MCP para V2:

Con este MCP activado, podré:
1. **Crear Repositorios y Ramas:** Podré iniciar el repositorio `PQRS_V2` directamente, crear ramas como `feature/kafka-ingestion` y aislar el desarrollo.
2. **Revisar Pull Requests (PRs):** Si tú u otro desarrollador escribe un código, podré leer los commits, encontrar bugs invisibles y aprobarlos antes de que vayan a la rama `main` (Producción).
3. **Buscar en Código Global:** Si no recordamos cómo configuramos Stripe en un proyecto pasado, podré buscar en todo tu GitHub esa línea de código instantáneamente.
4. **Gestionar Issues:** Podrás decirme: *"Crea un ticket (Issue) que diga que falta arreglar el botón de Login de Abogados Recovery"* y lo crearé en el tablero web de tu Github.

---

## 💻 Instalación y Configuración

El servidor oficial es provisto por la comunidad de Model Context Protocol y requiere un **Token de Acceso de GitHub**.

### Paso 1: Generar el Token (Personal Access Token)
1. Ve a [GitHub - Tokens Clásicos](https://github.com/settings/tokens).
2. Haz clic en **Generate new token (classic)**.
3. Dale un nombre (ej. `MCP-Cursor`).
4. Márcale los permisos principales: `repo` (todo el control de código privado/publico) y `admin:org` (si usas organizaciones).
5. Dale a generar y **copia el código secreto** que empiece con `ghp_...` (No lo compartas con humanos, sólo con tu entorno local).

### Paso 2: Conectar en Cursor
1. Ve a **Settings > Features > MCP Servers** en Cursor.
2. Haz clic en **+ Add New MCP Server**.
3. Rellena los datos:
   - **Name:** `github`
   - **Type:** `command`
   - **Command:**
     ```bash
     npx -y -y @modelcontextprotocol/server-github
     ```
4. **IMPORTANTE:** Abajo del comando, verás una sección llamada `Environment Variables` (Variables de entorno). Debes agregar una nueva variable:
   - **Key:** `GITHUB_PERSONAL_ACCESS_TOKEN`
   - **Value:** *(Pega aquí el código `ghp_...` que copiaste en el Paso 1)*

5. Toca **Save**. El indicador debe ponerse verde.

---

### ¿Cómo probarlo juntos?
Una vez que la bolita esté verde, ponme a prueba en el chat:
*"IA, búscame mis últimos 3 repositorios creados en mi cuenta de GitHub"* o *"Inicia un repositorio privado nuevo llamado PQRS_V2_Core"*

Al momento ejecutaré los comandos mágicos y lo tendré listo.
