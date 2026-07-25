# backend/services.py
# Regras de negócio para cálculo das métricas
from datetime import datetime, timedelta, timezone
from pymongo import ASCENDING
from config import OVERRIDE_MANUAL_SEGUNDOS, TZ_LOCAL
from database import db

# calcula métricas do dia anterior e persiste na coleção metricas
# chamada manualmente via endpoint ou automaticamente via job
#
# `data` identifica o dia pela sua DATA CIVIL (ano/mês/dia), interpretada em
# TZ_LOCAL — o fuso do datetime recebido é ignorado de propósito. Assim
# agregar_dia(datetime(2026, 7, 20, ...)) sempre significa "o dia 20 local",
# sem depender de o chamador ter passado UTC ou local. Se em vez disso
# convertêssemos o instante para local, meia-noite UTC do dia 20 viraria 21h do
# dia 19 e a função agregaria o dia errado.
def agregar_dia(data: datetime = None):
    if data is None:
        data = datetime.now(TZ_LOCAL) - timedelta(days=1)

    # as duas meia-noites que delimitam o dia, em horário de parede local.
    # timedelta sobre datetime aware faz aritmética de relógio de parede, então
    # somar um dia continua dando "meia-noite do dia seguinte" mesmo numa
    # transição de horário de verão.
    inicio_local   = datetime(data.year, data.month, data.day, tzinfo=TZ_LOCAL)
    proximo_local  = inicio_local + timedelta(days=1)

    # convertidas para UTC antes de qualquer uso. isso não é cosmético: quando os
    # dois operandos de uma subtração compartilham o MESMO objeto tzinfo — e o
    # ZoneInfo é cacheado, então compartilham — o Python subtrai os valores
    # ingênuos e ignora os offsets. Sem a conversão, um dia de 25h daria 24h aqui.
    # Em UTC os offsets são todos zero e a aritmética passa a ser sempre correta,
    # inclusive contra os timestamps dos eventos, que também vêm em UTC.
    inicio_dia     = inicio_local.astimezone(timezone.utc)
    proximo_inicio = proximo_local.astimezone(timezone.utc)
    fim_dia        = proximo_inicio - timedelta(microseconds=1)

    # duração real do dia, em vez de 86400 fixo: num dia de transição de horário
    # de verão o dia tem 23h ou 25h. O Brasil não tem HV desde 2019, mas o valor
    # fixo erraria dois dias por ano em silêncio se voltasse.
    segundos_do_dia = (proximo_inicio - inicio_dia).total_seconds()

    eventos = list(db.eventos.find(
        {"timestamp": {"$gte": inicio_dia, "$lte": fim_dia}},
        sort=[("timestamp", ASCENDING)]
    ))

    # o led pode já estar aceso/apagado desde ANTES da meia-noite (ninguém
    # necessariamente gera um evento exatamente no início do dia). por isso
    # buscamos o evento mais recente anterior a inicio_dia: ele nos diz qual
    # era o estado do LED no instante em que o dia começou. Sem isso, o tempo
    # apagado entre meia-noite e o primeiro evento do dia seria perdido.
    ultimo_evento_anterior = db.eventos.find_one(
        {"timestamp": {"$lt": inicio_dia}},
        sort=[("timestamp", -1)]
    )
    estado_atual = ultimo_evento_anterior["led"] if ultimo_evento_anterior else "off"

    # a origem do estado corrente entra no cálculo junto com o estado: só conta
    # como economia o tempo apagado por decisão dos sensores. eventos antigos e
    # firmware anterior não têm o campo, então a ausência é lida como "sensor".
    origem_atual = ultimo_evento_anterior.get("origem", "sensor") if ultimo_evento_anterior else "sensor"

    # só não há o que agregar se não houver eventos no dia E nenhum histórico
    # anterior que defina um estado inicial (dia sem nenhum dado, mesmo)
    if not eventos and ultimo_evento_anterior is None:
        print("Nenhum evento para agregar em:", data.date())
        return None

    # percorremos o dia com um "cursor" de tempo, contando o tempo apagado
    # segmento a segmento (do estado anterior até o próximo evento), em vez
    # de somar só os intervalos ENTRE eventos consecutivos. isso resolve dois
    # buracos da versão anterior:
    #   1. tempo apagado antes do primeiro evento do dia (ponta inicial,
    #      coberto pelo estado_atual vindo de ultimo_evento_anterior acima);
    #   2. tempo apagado depois do último evento do dia até a meia-noite
    #      seguinte (ponta final, tratada após o loop).
    tempo_apagado_s = 0
    cursor = inicio_dia

    for evento in eventos:
        if estado_atual == "off" and origem_atual == "sensor":
            tempo_apagado_s += (evento["timestamp"] - cursor).total_seconds()
        cursor = evento["timestamp"]
        estado_atual = evento["led"]
        origem_atual = evento.get("origem", "sensor")

    # ponta final: se o LED segue apagado após o último evento, esse tempo
    # até o fim do dia também conta (senão o loop acima nunca o soma, já que
    # não há um "próximo evento" para fechar o intervalo)
    if estado_atual == "off" and origem_atual == "sensor":
        tempo_apagado_s += (fim_dia - cursor).total_seconds()

    percentual_economia = (tempo_apagado_s / segundos_do_dia) * 100

    metrica = {
        "data"               : inicio_dia,
        "total_eventos"      : len(eventos),
        "tempo_apagado_s"    : tempo_apagado_s,
        "percentual_economia": round(percentual_economia, 2)
    }

    # upsert: atualiza se já existir métrica para esse dia, insere se não
    db.metricas.update_one(
        {"data": inicio_dia},
        {"$set": metrica},
        upsert=True
    )

    print("Métrica agregada para", data.date(), ":", metrica)
    return metrica

# agrega todo dia já encerrado que ainda não tem métrica.
# chamada no startup e pelo job diário (ver lifespan em main.py): como a API não
# fica de pé 24h, o disparo agendado das 00:05 frequentemente não acontece, e sem
# essa varredura os dias em que o processo estava parado nunca seriam agregados —
# os eventos brutos daquele dia sumiriam com o TTL de 7 dias e a métrica ficaria
# impossível de calcular depois.
def agregar_pendentes():
    primeiro_evento = db.eventos.find_one(sort=[("timestamp", ASCENDING)])
    if primeiro_evento is None:
        return []

    hoje = datetime.now(TZ_LOCAL).replace(hour=0, minute=0, second=0, microsecond=0)

    # varremos dia a dia em vez de olhar só os dias que têm evento: um dia sem
    # nenhuma transição (LED no mesmo estado do início ao fim) também merece
    # métrica, e agregar_dia() sabe calculá-la a partir do último evento anterior.
    # o intervalo é curto por construção — o TTL mantém no máximo ~7 dias de eventos.
    #
    # o timestamp vem do Mongo em UTC; convertemos para TZ_LOCAL antes de truncar,
    # senão a fronteira do dia sairia em UTC e a varredura discordaria de agregar_dia()
    dia = (primeiro_evento["timestamp"]
           .astimezone(TZ_LOCAL)
           .replace(hour=0, minute=0, second=0, microsecond=0))

    # tz_aware=True no MongoClient faz estas datas voltarem em UTC. A comparação
    # com `dia` (aware em TZ_LOCAL) funciona porque datetimes aware comparam e
    # hasheiam por instante, não por relógio de parede: meia-noite local e o
    # 03:00Z equivalente são o mesmo elemento do set.
    dias_com_metrica = set(db.metricas.distinct("data"))

    agregados = []
    while dia < hoje:  # o dia corrente fica de fora: ainda não terminou, e uma
                       # métrica parcial gravada agora nunca seria recalculada
                       # depois (o dia deixaria de constar como pendente)
        if dia not in dias_com_metrica and agregar_dia(dia) is not None:
            agregados.append(dia)
        dia += timedelta(days=1)

    if agregados:
        print("Dias pendentes agregados:", [d.date().isoformat() for d in agregados])
    return agregados

# estado corrente do sistema, derivado do último evento recebido.
# existe por um motivo específico: o timer do override manual roda no ESP32, e
# quando ele expira sem que a decisão dos sensores mude o estado do LED, nenhum
# evento novo é publicado. o último evento do banco continua sendo o manual
# indefinidamente, então quem consome /eventos não tem como saber que o override
# já caiu. aqui o backend reproduz a contagem a partir do timestamp do evento.
def estado_corrente():
    ultimo = db.eventos.find_one(sort=[("timestamp", -1)])

    if ultimo is None:
        return {
            "led": None, "origem": None, "modo": "automatico",
            "override_expira_em": None, "distancia": None,
            "luminosidade": None, "timestamp": None,
        }

    origem = ultimo.get("origem", "sensor")
    modo = "automatico"
    override_expira_em = None

    if origem == "manual":
        expira_em = ultimo["timestamp"] + timedelta(seconds=OVERRIDE_MANUAL_SEGUNDOS)
        # só está em override se a janela ainda não fechou; passado esse ponto o
        # ESP32 já voltou a decidir pelos sensores, mesmo sem ter publicado nada
        if datetime.now(timezone.utc) < expira_em:
            modo = "manual"
            override_expira_em = expira_em

    return {
        "led"               : ultimo["led"],
        "origem"            : origem,
        "modo"              : modo,
        "override_expira_em": override_expira_em,
        "distancia"         : ultimo.get("distancia"),
        "luminosidade"      : ultimo.get("luminosidade"),
        "timestamp"         : ultimo["timestamp"],
    }
