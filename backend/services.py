# backend/services.py
# Regras de negócio para cálculo das métricas
from datetime import datetime, timedelta, timezone
from pymongo import ASCENDING
from database import db

# calcula métricas do dia anterior e persiste na coleção metricas
# chamada manualmente via endpoint ou automaticamente via job
def agregar_dia(data: datetime = None):
    if data is None:
        data = datetime.now(timezone.utc) - timedelta(days=1)

    inicio_dia = data.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    fim_dia    = data.replace(hour=23, minute=59, second=59, microsecond=999999)

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
        if estado_atual == "off":
            tempo_apagado_s += (evento["timestamp"] - cursor).total_seconds()
        cursor = evento["timestamp"]
        estado_atual = evento["led"]

    # ponta final: se o LED segue apagado após o último evento, esse tempo
    # até o fim do dia também conta (senão o loop acima nunca o soma, já que
    # não há um "próximo evento" para fechar o intervalo)
    if estado_atual == "off":
        tempo_apagado_s += (fim_dia - cursor).total_seconds()

    percentual_economia = (tempo_apagado_s / 86400) * 100

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
