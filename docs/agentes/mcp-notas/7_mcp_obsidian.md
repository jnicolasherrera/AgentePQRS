# 🧠 MCP 7: Obsidian-MCP (El "Cerebro" y Gestor de Tareas)

A medida que el ecosistema **PQRS_V2** (Backend, Frontend, Landing Page, Kafka, Docker) crezca, no podemos depender de chats efímeros para recordar la arquitectura y las tareas pendientes. Necesitamos un **"Segundo Cerebro"**.

**Obsidian** es la herramienta perfecta para esto porque guarda tus notas puramente en archivos `.md` locales en tu computadora. Al conectar un MCP a Obsidian, tu Inteligencia Artificial (Antigravity/Cursor) obtiene **Memoria a Largo Plazo y Gestión NDE (No-Dependiente de la Nube)**.

## 🚀 ¿Qué haremos con este MCP?

1. **La Central de Tareas (Roadmap):** Crearemos una nota en Obsidian llamada `TABLERO_V2.md`. Tú escribirás allí (con casillas `[ ]`) cosas como *"Diseñar Landing Page con Google Stitch"* o *"Pasar Base a PostgreSQL"*. Yo leeré esa nota, ejecutaré el código y cuando termine, iré automáticamente a tu Obsidian a marcarla con una `[x]` y agregar mis comentarios técnicos.
2. **Registro de Arquitectura (PRD):** Almacenare los enlaces de Figma, los tokens de prueba, IPs de servidores y las reglas de esquema de base de datos allí. Si dentro de 3 meses volvemos a tocar la V2 y el chat se borró, le diré a mi MCP *"Lee toda la carpeta 'Arquitectura' de Obsidian"* y recordaré el proyecto en milisegundos.

## 💻 Instalación (Obsidian MCP)

Actualmente la comunidad mantiene varios conectores. Usaremos el conector de bóvedas locales.

### Paso 1: Configura tu "Bóveda" en Obsidian
1. Abre Obsidian. Si aún no tienes una, crea una nueva **Bóveda (Vault)** (Ej: guárdala en `E:\COLOMBIA\Obsidian_Brain`).
2. Abre tu IDE Cursor.

### Paso 2: Conectar el MCP en Cursor
1. Ve a **Settings (Configuración) > Features > MCP Servers** en Cursor.
2. Haz clic en **+ Add New MCP Server**.
3. Rellena los datos para permitir el acceso a tu disco local de notas:
   - **Name (Nombre):** `obsidian-mcp`
   - **Type (Tipo):** Selecciona `command`
   - **Command (Comando):**
     ```bash
     npx -y @modelcontextprotocol/server-memory
     ```
     *(Nota: Existe también la alternativa `npx -y -y @smithery/cli run @cyanheads/obsidian-mcp` que requiere configuración adicional dentro del propio plugin de Obsidian. Recomiendo comenzar con el servidor base de memoria local leyendo la bóveda).*

4. Toca **Save** y verifica la luz verde.

---

### 🔥 Flujo de Trabajo (Tú + IA + Obsidian)
1. Escribes en Obsidian: *"Idea: Agregar Stripe para cobrarle cuotas a FlexFintech"*.
2. Vas al chat de código y me dices: *"Busca mi última idea de negocio en Obsidian y empieza a programarla"*.
3. Yo la leo silenciosamente, instalo la dependencia en Node/Python, escribo el código y retorno a Obsidian para anotar: *"Suscripción de Stripe agregada en el archivo payment.py el 21/02/2026"*.
