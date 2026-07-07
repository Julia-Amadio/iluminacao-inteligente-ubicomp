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

    if not eventos:
        print("Nenhum evento para agregar em:", data.date())
        return None

    # calcula tempo total com LED apagado (autonomamente)
    tempo_apagado_s = 0
    for i in range(len(eventos) - 1):
        if eventos[i]["led"] == "off":
            delta = (eventos[i + 1]["timestamp"] - eventos[i]["timestamp"]).total_seconds()
            tempo_apagado_s += delta

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
