# backend/mqtt_client.py: conexao com o broker como subscriber
# Insere json de eventos na coleção do MongoDB
# Importa de config.py e database.py. A fila_eventos fica aqui também.
import json
import queue
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORTA, MQTT_TOPICO, MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD
from database import db

# singleton da fila. criado aqui, importado por quem precisar
# atualmente só main.py precisa dela para iniciar o worker
# thread-safe entre o subscriber MQTT e o handler de inserção no Mongo
# o subscriber roda numa thread separada e deposita aqui;
# o handler consome daqui e insere no Mongo
fila_eventos: queue.Queue = queue.Queue()

def _inserir_evento(payload: dict):
    documento = {
        "led"         : payload.get("led"),           # "on" ou "off"
        "distancia"   : payload.get("distancia"),     # float cm ou None
        "luminosidade": payload.get("luminosidade"),  # int 0–4095
        "timestamp": datetime.now(timezone.utc)       # anexado pelo backend
    }
    db.eventos.insert_one(documento)
    print("Evento inserido:", documento)

# Worker de inserção
# roda numa thread separada, consome a fila e insere no Mongo
# desacopla o subscriber MQTT (que precisa ser rápido) da escrita no banco
def worker_insercao():
    """
    Roda em thread separada.
    Consome fila_eventos indefinidamente e insere no Mongo.
    Desacopla a escrita no banco do loop MQTT,
    evitando que uma inserção lenta atrase o recebimento de mensagens.
    """
    while True:
        payload = fila_eventos.get()  # bloqueia até haver item na fila
        try:
            _inserir_evento(payload)
        except Exception as e:
            print("Erro ao inserir evento:", e)
        finally:
            fila_eventos.task_done()

def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Subscriber MQTT conectado ao broker")
        client.subscribe(MQTT_TOPICO)
        print("Assinando tópico:", MQTT_TOPICO)
    else:
        print("Falha na conexão MQTT, código:", rc)

def _on_message(client, userdata, msg):
    """
    Callback do paho. Chamado na thread do loop MQTT.
    Só deposita na fila e retorna imediatamente;
    a inserção no Mongo acontece no worker_insercao().
    """
    try:
        payload = json.loads(msg.payload.decode())
        print("Mensagem recebida:", payload)
        fila_eventos.put(payload)  # deposita na fila; worker cuida da inserção
    except Exception as e:
        print("Erro ao processar mensagem:", e)

def iniciar_subscriber():
    """
    Roda em thread separada (daemon).
    Cria o cliente paho, configura callbacks e bloqueia em loop_forever().
    O cliente paho é local a essa função, não precisa ser singleton
    porque só existe uma instância dele e só essa thread o acessa.
    """
    cliente = mqtt.Client(client_id=MQTT_CLIENT_ID)

    # autenticação, só configura se as credenciais estiverem na .env
    if MQTT_USER and MQTT_PASSWORD:
        cliente.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        cliente.tls_set()  # broker privado HiveMQ exige TLS na porta 8883

    cliente.on_connect = _on_connect
    cliente.on_message = _on_message
    cliente.connect(MQTT_BROKER, MQTT_PORTA, keepalive=60)
    cliente.loop_forever()  # bloqueia a thread, paho gerencia reconexões internamente
