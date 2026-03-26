# Infraestructura: Prerequisitos Locales

## Requisitos del Sistema

- **OS:** Ubuntu 24+ (probado) / macOS / Windows con WSL2
- **Docker:** Docker Engine 24+ con Docker Compose v2
- **Node.js:** v18+ (v20 recomendado) para MCPs via npx
- **Python:** 3.11+ (usado en el backend Dockerfile)

## Instalacion Rapida (Ubuntu)

```bash
# Docker (si no esta instalado)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Node.js 20 (para MCPs)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verificar
docker --version
docker compose version
node -v
```

## Variables de Entorno Requeridas

Crear archivo `.env` en la raiz del proyecto o exportar:

```bash
# Obligatorias para produccion
JWT_SECRET_KEY=una-clave-secreta-fuerte-aqui
ANTHROPIC_API_KEY=sk-ant-...

# Outlook (si se usa Microsoft Graph)
AZURE_CLIENT_SECRET=...
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...

# Gmail demo (fallback SMTP)
DEMO_GMAIL_PASSWORD=...
```

## Puertos Utilizados

| Servicio    | Puerto Host | Puerto Container |
|-------------|-------------|------------------|
| PostgreSQL  | 5434        | 5432             |
| Redis       | 6381        | 6379             |
| ZooKeeper   | 2182        | 2181             |
| Kafka       | 9093        | 9092             |
| MinIO API   | 9020        | 9000             |
| MinIO UI    | 9021        | 9001             |
| Backend     | 8001        | 8000             |
| Frontend    | 3002        | 3000             |
| Nginx HTTP  | 80          | 80               |
| Nginx HTTPS | 443         | 443              |

Asegurar que estos puertos no esten en uso antes de arrancar.


## Referencias

- [[02_INFRA_DOCKER_COMPOSE_ARRANQUE]]
- [[05_DB_ESQUEMA_Y_ROLES]]
