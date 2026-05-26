import requests
import time

# Configuración
UBUNTU_IP = "192.168.0.248"
BACKEND_URL = f"http://{UBUNTU_IP}:8000"

def test_connection():
    print(f"--- 🔍 Verificando conexión con Ubuntu ({UBUNTU_IP}) ---")
    try:
        r = requests.get(f"{BACKEND_URL}/")
        print(f"Respuesta del API: {r.json()}")
        return True
    except Exception as e:
        print(f"❌ No se pudo conectar con el Ubuntu: {e}")
        return False

if __name__ == "__main__":
    if test_connection():
        print("\n🚀 ¡Éxito! Tu servidor Ubuntu está encendido y escuchando.")
        print("Ahora puedes entrar a http://192.168.0.248:3000 desde este Chrome.")
    else:
        print("\n⚠️ Verifica que el script './deploy_ubuntu.sh' haya terminado en la otra PC.")
