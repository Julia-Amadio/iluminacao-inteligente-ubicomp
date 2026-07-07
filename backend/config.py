# backend/config.py: credenciais MongoDB e constantes do broker.
# não importa nada interno, só os e dotenv. Todos os outros importam dele.
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI      = os.getenv("MONGO_URI")

MQTT_BROKER    = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORTA     = int(os.getenv("MQTT_PORTA", 1883))
MQTT_TOPICO    = os.getenv("MQTT_TOPICO", "pervasiva/grupo1/iluminacao")
MQTT_CLIENT_ID = "backend_grupo1_subscriber"
MQTT_USER      = os.getenv("MQTT_USER", None)
MQTT_PASSWORD  = os.getenv("MQTT_PASSWORD", None)
