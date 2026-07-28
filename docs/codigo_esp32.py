from machine import Pin, ADC, time_pulse_us
import network
import time
import ujson
from umqtt.simple import MQTTClient

# -------------------------- Configuração dos pinos --------------------------
# Acho que não mudamos nada aqui na última aula... confirmar please
TRIG_PIN = 5
ECHO_PIN = 18
LED_PIN  = 4
LDR_PIN  = 34

LIMIAR_DISTANCIA_CM = 50
LIMIAR_LUMINOSIDADE = 1500

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
led  = Pin(LED_PIN,  Pin.OUT)

ldr = ADC(Pin(LDR_PIN))
ldr.atten(ADC.ATTN_11DB)
ldr.width(ADC.WIDTH_12BIT)

# -------------------------- Configuração Wi-Fi ------------------------------
# PREENCHER ao colar no Thonny, e NÃO comitar os valores reais: este arquivo é
# versionado num repositório público.
WIFI_SSID  = "SSID_nome_do_wifi"
WIFI_SENHA = "senha_do_wifi"

# -------------------------- Configuração MQTT -------------------------------
MQTT_BROKER    = "broker.hivemq.com"
MQTT_PORTA     = 1883
MQTT_CLIENT_ID = "esp32_grupo1_caetanoubicomp"   # deve ser único no broker

MQTT_TOPICO          = "pervasiva/grupo1/iluminacao"           # publica eventos
MQTT_TOPICO_CONTROLE = "pervasiva/grupo1/iluminacao/controle"  # assina comandos

# ---------------------- Configuração do override manual ---------------------
# Quanto tempo um comando do dashboard sobrepõe a decisão dos sensores.
# PRECISA bater com OVERRIDE_MANUAL_SEGUNDOS em backend/config.py: o backend
# reproduz essa mesma contagem para informar o modo atual em GET /estado, já que
# o timer de verdade roda aqui.
OVERRIDE_MANUAL_MS = 5 * 60 * 1000   # 5 minutos

# Cadência do loop principal. Os comandos MQTT são checados numa cadência bem
# mais curta que a leitura dos sensores — se a checagem acontecesse só uma vez
# por ciclo de sensor, um comando do dashboard poderia esperar 1s inteiro.
INTERVALO_SENSOR_MS   = 1000
INTERVALO_CHECAGEM_MS = 100

# --------------------------- Estado do override -----------------------------
# override_estado guarda o "on"/"off" pedido pelo dashboard; override_expira_em
# é o instante (em ticks_ms) a partir do qual esse pedido deixa de valer.
# Ambos None significa que a decisão está com a fusão de contexto dos sensores.
override_estado    = None
override_expira_em = None

# Avisa o loop principal que chegou comando e ele deve reagir imediatamente,
# sem esperar o próximo tick de leitura dos sensores.
comando_pendente = False

# ----------------------- Conexão Wi-Fi --------------------------------------
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_SENHA)

    print("Conectando ao Wi-Fi", end="")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep_ms(500)   # sleep() recebe SEGUNDOS em MicroPython; sleep_ms() é o certo aqui

    print("\nWi-Fi conectado:", wlan.ifconfig()[0])

# ----------------------- Recebimento de comandos ----------------------------
def ao_receber_comando(topico, mensagem):
    """
    Callback do umqtt, chamado de dentro de check_msg().
    Só registra o override e sai: aplicar o estado e publicar o evento fica para
    o loop principal. Publicar aqui usaria o mesmo socket que está no meio de uma
    leitura, e o umqtt.simple não é reentrante.
    """
    global override_estado, override_expira_em, comando_pendente

    try:
        comando = ujson.loads(mensagem)
    except Exception:
        print("Comando ignorado, JSON inválido:", mensagem)
        return

    estado_pedido = comando.get("led")
    if estado_pedido not in ("on", "off"):
        print("Comando ignorado, campo led inválido:", comando)
        return

    # A origem é fixada como "manual" aqui em vez de lida do payload: qualquer
    # mensagem que chegue neste tópico é, por definição, comando manual. Confiar
    # no campo do payload permitiria publicar um comando marcado como "sensor" e
    # falsear a métrica de economia autônoma.
    override_estado    = estado_pedido
    override_expira_em = time.ticks_add(time.ticks_ms(), OVERRIDE_MANUAL_MS)
    comando_pendente   = True
    print(">> Comando manual recebido:", estado_pedido)

# ----------------------- Conexão MQTT ---------------------------------------
def conectar_mqtt():
    cliente = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, MQTT_PORTA)
    cliente.set_callback(ao_receber_comando)
    cliente.connect()
    cliente.subscribe(MQTT_TOPICO_CONTROLE, qos=1)
    print("MQTT conectado ao broker:", MQTT_BROKER)
    print("Assinando tópico de controle:", MQTT_TOPICO_CONTROLE)
    return cliente

def reconectar(cliente):
    """
    Reconecta e REASSINA o tópico de controle.
    A reinscrição não é opcional: o broker descarta as assinaturas quando a
    conexão cai, então reconectar sem assinar de novo deixa o ESP32 publicando
    normalmente mas surdo a comandos — falha silenciosa e difícil de perceber.
    """
    try:
        cliente.connect()
        cliente.subscribe(MQTT_TOPICO_CONTROLE, qos=1)
        print("Reconectado e reinscrito em:", MQTT_TOPICO_CONTROLE)
        return True
    except Exception as e:
        print("Reconexão falhou:", e)
        return False

def verificar_comandos(cliente):
    """
    check_msg() é não-bloqueante: processa uma mensagem pendente e retorna, ou
    retorna None se não houver nada. É o que permite intercalar a escuta do
    tópico de controle com a leitura dos sensores num único loop.
    """
    try:
        cliente.check_msg()
    except Exception as e:
        print("Erro ao checar mensagens, reconectando:", e)
        reconectar(cliente)

# ---------------------- Função de medição de distância ----------------------
def medir_distancia():
    trig.off()
    time.sleep_us(2)
    trig.on()
    time.sleep_us(10)
    trig.off()

    duracao_us = time_pulse_us(echo, 1, 30000)

    if duracao_us < 0:
        return None

    return duracao_us / 58

# --------------------- Função de leitura de luminosidade --------------------
def medir_luminosidade():
    leituras = [ldr.read() for _ in range(5)]
    return sum(leituras) // len(leituras)

# --------------------- Função de decisão de acionamento --------------------
def avaliar_contexto(distancia, luminosidade):
    # LIMIAR_DISTANCIA_CM = 50 | LIMIAR_LUMINOSIDADE = 1500
    presenca = distancia is not None and distancia < LIMIAR_DISTANCIA_CM
    escuro   = luminosidade < LIMIAR_LUMINOSIDADE
    return presenca and escuro

def decidir_estado(distancia, luminosidade):
    """
    Devolve (estado, origem).
    O override manual tem prioridade enquanto a janela estiver aberta; quando ela
    fecha, o override é descartado e a fusão de contexto volta a decidir.
    """
    global override_estado, override_expira_em

    if override_expira_em is not None:
        # ticks_diff trata o wraparound de ticks_ms; subtração crua quebraria
        if time.ticks_diff(override_expira_em, time.ticks_ms()) > 0:
            return override_estado, "manual"

        print(">> Override manual expirou, devolvendo controle aos sensores")
        override_estado    = None
        override_expira_em = None

    return ("on" if avaliar_contexto(distancia, luminosidade) else "off"), "sensor"

# --------------------- Função de publicação MQTT ----------------------------
def publicar_evento(cliente, estado_led, origem, distancia, luminosidade):
    payload = ujson.dumps({
        "led"         : estado_led,      # "on" ou "off"
        "origem"      : origem,          # "sensor" ou "manual"
        "distancia"   : distancia,       # float em cm, ou None
        "luminosidade": luminosidade     # int 0–4095
    })

    try:
        cliente.publish(MQTT_TOPICO, payload)
        print("Publicado:", payload)
    except Exception as e:
        print("Erro ao publicar, tentando reconectar:", e)
        if reconectar(cliente):
            try:
                cliente.publish(MQTT_TOPICO, payload)
                print("Publicado após reconexão:", payload)
            except Exception as e2:
                print("Publicação falhou de novo, evento perdido:", e2)

# ------------------------------ Inicialização -------------------------------
conectar_wifi()
cliente_mqtt = conectar_mqtt()

# estado e origem anteriores — controlam quando publicar.
# começam como None para forçar a publicação na primeira iteração
estado_anterior = None
origem_anterior = None

ultimo_ciclo = time.ticks_ms()

# ------------------------------ Loop principal ------------------------------
while True:
    verificar_comandos(cliente_mqtt)

    agora       = time.ticks_ms()
    hora_de_ler = time.ticks_diff(agora, ultimo_ciclo) >= INTERVALO_SENSOR_MS

    # um comando recém-recebido faz o ciclo rodar na hora, sem esperar o tick
    if comando_pendente or hora_de_ler:
        comando_pendente = False
        ultimo_ciclo     = agora

        distancia    = medir_distancia()
        luminosidade = medir_luminosidade()

        if distancia is not None:
            dist_str = "{:.1f} cm".format(distancia)
        else:
            dist_str = "fora de alcance"

        estado_atual, origem_atual = decidir_estado(distancia, luminosidade)

        print("Distância: {} | Luminosidade: {} | Decisão: {}".format(
            dist_str, luminosidade, origem_atual))

        # aciona o LED
        led.value(1 if estado_atual == "on" else 0)

        # publica quando muda o estado OU a origem. incluir a origem é o que faz
        # o backend enxergar o começo e o fim do override: um comando manual que
        # pede o estado em que o LED já está não muda "led", mas muda quem está
        # decidindo — e agregar_dia() precisa desse marco para parar de contar o
        # intervalo como economia autônoma.
        if (estado_atual, origem_atual) != (estado_anterior, origem_anterior):
            print(">> Transição: {}/{} -> {}/{}".format(
                estado_anterior, origem_anterior, estado_atual, origem_atual))
            publicar_evento(cliente_mqtt, estado_atual, origem_atual,
                            distancia, luminosidade)
            estado_anterior = estado_atual
            origem_anterior = origem_atual

    time.sleep_ms(INTERVALO_CHECAGEM_MS)
