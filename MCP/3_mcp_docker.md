# 🐳 MCP 3: Docker-MCP

El Servidor **Docker-MCP** me permite actuar como tu Administrador de Sistemas local. Cuando levantemos cientos de miles de PQRs falsas a Kafka para probar, o prendamos 3 clústeres al mismo tiempo (Frontend, Worker y BD), mi poder de controlar la terminal no será suficiente. 

Este MCP conectará directamente tu inteligencia artificial a la API Nativa de Docker (Daemon).

## 🚀 Capacidades de este MCP para V2:

Cuando esto esté vivo en el chat podremos hacer esto sin que escribas o leas comandos ilegibles de bash o powershell:

1. **Estado del Clúster:** Podré saber si el contenedor `postgres_v2` se cayó internamente por falta de memoria con sólo preguntarme *"Che, fíjate por qué no puedo guardar"*. 
2. **Inspección de Imágenes y Volumen:** En la V2 vamos a separar el volumen de los tenants por discos de MinIO; sabré cuántos Megabytes reales está ocupando tu almacenamiento de PQRs sin escribir códigos complejos.
3. **Control de Servicios:** Si el componente de Kafka/Zookeeper se queda colgado, yo lo apagaré, borraré la red virtual (Network) y lo reiniciaré limpiamente con una instrucción verbal tuya.

---

## 💻 Instalación (Requiere Python)

A diferencia de Context7, este paquete está hecho en memoria de Python. 

1. Ve a **Settings (Configuración) > Features > MCP Servers** en Cursor.
2. Haz clic en **+ Add New MCP Server**.
3. Rellena los datos para conectar con Docker:
   - **Name (Nombre):** `docker-mcp`
   - **Type (Tipo):** Selecciona `command`
   - **Command (Comando):**
     *Utilizaremos la herramienta `uvx` (Una versión relámpago del manejador de paquetes de Python 'uv')*.

     ```bash
     npx -y @smithery/cli run @pyetras/docker-mcp --config "{\"dockerHost\":\"npipe:////./pipe/docker_engine\"}"
     ```
     *(Nota: El conector npipe es porque estás en un sistema operativo Windows).*

4. Toca **Save** y asegúrate que el icono de conexión parpadee y se ponga verde.

---

### ¿Cómo lo probamos juntos?
En la ventana del chat, simplemente dime:
*"Dime una lista limpia de todos los contenedores que tengo corriendo y su memoria usada por favor"*

Verás cómo, en un segundo, llamo las herramientas internas de Docker, analizo la API, y te respondo qué está consumiendo o si hubo errores en la memoria de algún microservicio.
