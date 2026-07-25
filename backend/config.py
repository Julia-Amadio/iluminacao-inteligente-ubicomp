# backend/config.py: credenciais MongoDB e constantes do broker.
# não importa nada interno, só os e dotenv. Todos os outros importam dele.
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import os

load_dotenv()

MONGO_URI      = os.getenv("MONGO_URI")

# Fuso usado para decidir A QUE DIA um evento pertence. Os timestamps continuam
# gravados em UTC (é o correto para instantes); este fuso só define onde cai a
# fronteira do dia nas agregações e nas consultas "de hoje".
#
# Importa porque padrões de ocupação seguem o horário local: com fronteira em UTC,
# um evento das 22h de Brasília cairia no dia seguinte da métrica.
#
# ZoneInfo em vez de offset fixo -3 de propósito: o Brasil aboliu o horário de
# verão em 2019, mas se voltar, um offset fixo erra silenciosamente metade do ano.
# Em Windows nativo o zoneinfo não acha o banco de fusos do sistema e exige
# `pip install tzdata`; em Linux/container funciona direto.
TZ_LOCAL = ZoneInfo(os.getenv("TZ_LOCAL", "America/Sao_Paulo"))

MQTT_BROKER    = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORTA     = int(os.getenv("MQTT_PORTA", 1883))
MQTT_TOPICO    = os.getenv("MQTT_TOPICO", "pervasiva/grupo1/iluminacao")
# Tópico onde os comandos manuais são publicados. O ESP32 assina este tópico; o
# frontend também publica nele direto por WebSocket, então os dois caminhos
# (POST /comando e browser) convergem no mesmo lugar.
MQTT_TOPICO_CONTROLE = os.getenv("MQTT_TOPICO_CONTROLE", "pervasiva/grupo1/iluminacao/controle")
MQTT_CLIENT_ID = "backend_grupo1_subscriber"
MQTT_USER      = os.getenv("MQTT_USER", None)
MQTT_PASSWORD  = os.getenv("MQTT_PASSWORD", None)

# Duração do override manual, em segundos. PRECISA ser o mesmo valor usado no
# firmware do ESP32 (docs/codigo_esp32.py), porque o timer de verdade roda lá:
# o backend só reproduz a contagem para poder informar o modo atual em GET /estado.
#
# ATENÇÃO: o default está em 10s TEMPORARIAMENTE, para não esperar 5 minutos a
# cada teste de expiração. O valor de entrega é 300 (5 min), e trocar aqui exige
# trocar OVERRIDE_MANUAL_MS no firmware junto — se os dois divergirem, GET /estado
# e o ESP32 passam a discordar sobre quando o override terminou.
OVERRIDE_MANUAL_SEGUNDOS = int(os.getenv("OVERRIDE_MANUAL_SEGUNDOS", 10))
