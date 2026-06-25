# 🛠️ MCP 1: mcp-postgres

Este Servidor MCP (Model Context Protocol) permite a tu Inteligencia Artificial (Antigravity/Cursor) conectarse **en tiempo real** y de forma segura a la nueva base de datos PostgreSQL de la V2. 

Con él activado, podré leer tus esquemas, validar si el Row-Level Security está funcionando, buscar información de los clientes sin pedirte que la pegues en el chat, y encontrar "cuellos de botella" analizando consultas lentas (EXPLAIN ANALYZE) cuando procesemos 1 millón de PQRs.

## ¿De dónde se descarga y cómo lo instalo?

Los MCPs no se descargan como un .exe normal. Se configuran **directamente dentro de las configuraciones de tu IDE (Cursor) o tu cliente de IA**. Tu cliente descargará y correrá este servidor invisible usando `npx` (Node Package Execute) en el fondo.

### Paso a paso de Instalación:

**1. Instalar NodeJS (Si no lo tienes)**
El MCP de PostgreSQL está programado oficialmente en TypeScript/Node. 
- Abre tu terminal y escribe `node -v`. Si te arroja un número (ej. `v18.x.x` o superior), estás listo. Si dice "comando no reconocido", descárgalo rápido desde [nodejs.org](https://nodejs.org/).

**2. Levantar la Base de Datos V2 (Docker de prueba)**
Antes de conectar el MCP, la base de datos PostgreSQL V2 debe estar encendida en tu computadora local.
*(Abre la terminal en la carpeta `E:\COLOMBIA\PQRS_V2` y ejecuta: `docker-compose up -d postgres_v2`)*

**3. Configurar el MCP en tu IDE (Cursor)**
Esta es la conexión mágica:
1. En Cursor, presiona `Ctrl + Shift + J` o ve a los **Settings (Configuración) > Features > MCP Servers**.
2. Haz clic en el botón de **+ Add New MCP Server** (Añadir nuevo servidor MCP).
3. Rellena los datos así:
   - **Name (Nombre):** `mcp-postgres-v2`
   - **Type (Tipo):** Selecciona `command`
   - **Command (Comando):** Pega exactamente esta línea:
     ```bash
     npx -y @modelcontextprotocol/server-postgres postgresql://pg_user:pg_password@localhost:5432/pqrs_v2
     ```
4. Guarda y activa (toggle ON) el servidor. Verás un circulito verde si la conexión a tu PostgreSQL fue exitosa.

---

### ✅ ¿Cómo probar que funcionó?
Una vez que el circulito esté verde, en el chat del IDE escríbeme:
*"Revisa qué tablas hay dentro del mcp-postgres-v2"*

Yo (la IA) usaré mis nuevas herramientas integradas para entrar a tu PostgreSQL local y responderte sin que me des ningún archivo. ¡Instálalo y avísame cuando esté listo para pasar al segundo MCP (Kafka)!
