#!/bin/bash

# Este script instala docker en Ubuntu 24 y levanta el proyecto completo (backend, frontend, bases de datos)

echo "=== Configurando PQRS_V2 en Ubuntu 24 ==="

# 1. Update system and install prerequisites
echo "Actualizando el sistema..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# 2. Add Docker's official GPG key
echo "Instalando llave de Docker..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Add Docker repository for Ubuntu
echo "Agregando repositorio de Docker..."
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker Engine, containerd, and Docker Compose plugin
echo "Instalando Docker Engine..."
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Add user to docker group so you don't need sudo for docker
sudo usermod -aG docker $USER
echo "Se ha agregado el usuario al grupo docker. Podría ser necesario cerrar y volver a iniciar sesión para que tome efecto."

# 6. Build and start containers with docker-compose
echo "Construyendo y levantando los contenedores de PQRS_V2..."
sudo docker compose build --no-cache
sudo docker compose up -d

echo "==========================================="
echo "Migración completada. Servicios iniciados en Docker."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "Para ver los logs de los contenedores usa:"
echo "sudo docker compose logs -f"
echo "==========================================="
