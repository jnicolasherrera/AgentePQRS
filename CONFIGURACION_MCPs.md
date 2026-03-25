# 🤖 Guía de Configuración de MCPs y Memoria en Ubuntu 24

Este archivo te guía para restaurar el ecosistema completo de herramientas de IA en tu computadora con Ubuntu 24.

---

## 📋 Pre-requisitos

Antes de activar los MCPs, asegúrate de tener instalados:

```bash
# Verifica Node.js (necesario para todos los MCPs via npx)
node -v    # Necesitas v18 o superior

# Si no lo tienes en Ubuntu 24:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verifica que Docker esté corriendo (luego de correr deploy_ubuntu.sh)
sudo docker compose ps
```

---

## 🧠 PASO 1: Memoria Obsidian (Bóveda de Conocimiento del Proyecto)

La bóveda está incluida en la carpeta **`Boveda_IA/`** que está dentro de este mismo proyecto.

1. Instala Obsidian para Linux desde [obsidian.md/download](https://obsidian.md/download) (descarga el `.AppImage` o `.deb`)
2. Abre Obsidian → **"Abrir carpeta como bóveda"** → selecciona la carpeta `Boveda_IA/` de este proyecto
3. ¡Ya tendrás toda la memoria y el tablero cargado!

---

## ⚙️ PASO 2: Archivo de Configuración MCP para Cursor / Antigravity

Crea o edita el archivo `.mcp.json` en la raíz del proyecto con este contenido.
Los contenedores Docker deben estar corriendo (`sudo docker compose up -d`) para que los MCPs de base de datos funcionen.

```json
{
  "mcpServers": {
    "mcp-postgres-v2": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://pqrs_admin:pg_password@localhost:5433/pqrs_v2"
      ]
    },
    "mcp-filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/ruta/del/proyecto/PQR-TUTELAS"
      ]
    },
    "mcp-obsidian": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "mcp-context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "mcp-github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "TU_GITHUB_TOKEN_AQUI"
      }
    }
  }
}
```

> ⚠️ **IMPORTANTE:** Cambia `/ruta/del/proyecto/PQR-TUTELAS` por la ruta real en tu Ubuntu (por ejemplo `/home/tu_usuario/PQR-TUTELAS`) y coloca tu token de GitHub real.

---

## 🎯 PASO 3: Skills Disponibles (ya incluidas en `.agents/skills/`)

Los Skills están copiados en la carpeta `.agents/skills/` de este mismo proyecto.
El agente IA los detectará automáticamente cuando abras el proyecto en Cursor.

| Skill                       | Para qué sirve                                         |
| --------------------------- | ------------------------------------------------------ |
| `event-driven-architect`    | Diseñar Kafka, Workers, Dead Letter Queues             |
| `postgres-rls-expert`       | Seguridad Multitenancy con RLS en PostgreSQL           |
| `kubernetes-cloud-engineer` | Despliegue en Kubernetes y autoescalado con KEDA       |
| `react-performance-master`  | SSE, virtualización de listas y performance en Next.js |

---

## ✅ Resumen del Orden de Arranque en Ubuntu

```bash
# 1. Levanta toda la infraestructura (BD, Redis, Kafka, Frontend, Backend)
sudo docker compose up -d

# 2. Verifica que todo está corriendo
sudo docker compose ps

# 3. Abre el proyecto en Cursor - los MCPs y Skills se cargan solos
# 4. Abre Obsidian apuntando a la carpeta Boveda_IA/

# Para ver logs en tiempo real:
sudo docker compose logs -f backend_v2
sudo docker compose logs -f frontend_v2
```

Servicios disponibles una vez levantado todo:

- 🌐 **Frontend:** http://localhost:3000
- 🔌 **Backend API:** http://localhost:8000
- 🐘 **PostgreSQL:** localhost:5433
- 🟥 **Redis:** localhost:6380
- 📦 **MinIO:** http://localhost:9011
- 📨 **Kafka:** localhost:9092
