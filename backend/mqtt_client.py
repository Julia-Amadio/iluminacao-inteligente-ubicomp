# backend/mqtt_client.py: conexao com o broker como subscriber
# Insere json de eventos na coleção do MongoDB
# Importa de config.py e database.py. A fila_eventos fica aqui também.
import json
import queue
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from config import (MQTT_BROKER, MQTT_PORTA, MQTT_TOPICO, MQTT_TOPICO_CONTROLE,
                    MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)
from database import db

# singleton da fila. criado aqui, importado por quem precisar
# atualmente só main.py precisa dela para iniciar o worker
# thread-safe entre o subscriber MQTT e o handler de inserção no Mongo
# o subscriber roda numa thread separada e deposita aqui;
# o handler consome daqui e insere no Mongo
fila_eventos: queue.Queue = queue.Queue()

# Cliente paho compartilhado. Construído aqui no import (construir não conecta);
# quem conecta e roda o loop de rede é iniciar_subscriber(), numa thread daemon.
#
# Ele precisa ser singleton de escopo de módulo — e não local à thread do
# subscriber, como era antes — porque POST /comando publica por ele a partir da
# thread HTTP. publish() do paho é thread-safe enquanto o loop de rede roda em
# outra thread, então os dois usos compartilham a mesma conexão e não é preciso
# abrir uma segunda.
cliente_mqtt = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=MQTT_CLIENT_ID,
)

def _inserir_evento(payload: dict):
    # led é o único campo que não pode ser confiado cegamente: distancia e
    # luminosidade são nuláveis por natureza (HC-SR04 fora de alcance devolve
    # None), mas um led inválido corrompe silenciosamente o cálculo de
    # agregar_dia(), que percorre a linha do tempo comparando esse valor com
    # "off". Um payload malformado inserido como None nunca casaria com "off"
    # e o tempo apagado sairia errado sem nenhum sinal de erro.
    led = payload.get("led")
    if led not in ("on", "off"):
        print("Payload descartado, campo led inválido:", payload)
        return

    documento = {
        "led"         : led,                          # "on" ou "off"
        "distancia"   : payload.get("distancia"),     # float cm ou None
        "luminosidade": payload.get("luminosidade"),  # int 0–4095
        # origem da transição: "sensor" (fusão de contexto do ESP32) ou "manual"
        # (comando do dashboard). O default cobre o firmware antigo e os eventos
        # já gravados no banco, que não têm esse campo — sem ele, agregar_dia()
        # trataria todo o histórico como se não fosse economia autônoma.
        "origem"      : payload.get("origem", "sensor"),
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

def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Subscriber MQTT conectado ao broker")
        client.subscribe(MQTT_TOPICO)
        print("Assinando tópico:", MQTT_TOPICO)
    else:
        print("Falha na conexão MQTT, código:", reason_code)

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

def publicar_comando(led: str) -> bool:
    """
    Publica um comando manual no tópico de controle. Chamada da thread HTTP pelo
    endpoint POST /comando.

    Devolve True quando a mensagem foi entregue ao loop de rede do paho — o que
    NÃO garante que o ESP32 recebeu nem agiu: ele pode estar desligado ou sem
    Wi-Fi. A confirmação real de atuação é o evento que o ESP32 publica de volta
    no tópico de eventos, visível depois em GET /eventos e GET /estado.

    A origem vai fixada como "manual" porque é o que este caminho significa; o
    firmware também não confia nesse campo e o refixa do lado dele.
    """
    payload = json.dumps({"led": led, "origem": "manual"})
    resultado = cliente_mqtt.publish(MQTT_TOPICO_CONTROLE, payload, qos=1)

    if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
        # com qos=1 e sem conexão o paho enfileira a mensagem para enviar quando
        # reconectar, mas devolve erro — então aqui ainda é honesto reportar falha
        print("Falha ao publicar comando, rc:", resultado.rc)
        return False

    print("Comando publicado em", MQTT_TOPICO_CONTROLE, ":", payload)
    return True

def iniciar_subscriber():
    """
    Roda em thread separada (daemon).
    Configura os callbacks do cliente compartilhado e bloqueia em loop_forever().
    """
    # autenticação, só configura se as credenciais estiverem na .env
    if MQTT_USER and MQTT_PASSWORD:
        cliente_mqtt.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        cliente_mqtt.tls_set()  # broker privado HiveMQ exige TLS na porta 8883

    cliente_mqtt.on_connect = _on_connect
    cliente_mqtt.on_message = _on_message
    cliente_mqtt.connect(MQTT_BROKER, MQTT_PORTA, keepalive=60)
    cliente_mqtt.loop_forever()  # bloqueia a thread, paho gerencia reconexões internamente
