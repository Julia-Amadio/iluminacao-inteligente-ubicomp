# backend/main.py
# Instancia FastAPI
# Importa de tudo. Monta o lifespan, registra os routers com app.include_router(), 
# e é o único arquivo que o uvicorn precisa conhecer.
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import TZ_LOCAL
from database import inicializar_banco
from mqtt_client import iniciar_subscriber, worker_insercao
from routers import comando, estado, eventos, metricas
from services import agregar_pendentes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # inicialização: roda antes de aceitar requisições
    inicializar_banco()

    # subscriber MQTT. daemon=True garante que morre junto com o processo principal
    threading.Thread(target=iniciar_subscriber, daemon=True).start()

    # worker de inserção no Mongo, consome fila_eventos
    threading.Thread(target=worker_insercao, daemon=True).start()

    # agregação de métricas: substitui o POST /metricas/agregar manual usado nos
    # testes (o endpoint continua existindo). agregar_pendentes() varre todo dia
    # encerrado sem métrica, então cobre tanto o caso normal quanto os dias em que
    # o processo estava parado na hora do disparo.
    #
    # roda duas vezes por motivos diferentes: aqui no startup, porque a API não
    # fica de pé 24h e o disparo das 00:05 quase nunca a encontra rodando; e no
    # job diário abaixo, para o caso de ela ficar de pé atravessando a virada.
    agregar_pendentes()

    # misfire_grace_time: o default do APScheduler é 1s — se a thread não conseguir
    # rodar o job dentro desse segundo (máquina sob carga, processo suspenso), o
    # disparo é descartado silenciosamente. 1h de tolerância absorve atrasos
    # transitórios; atrasos maiores que isso são cobertos pela varredura de
    # pendentes na próxima subida da API.
    # 00:05 no fuso LOCAL, não em UTC: o job agrega o dia que acabou de fechar, e
    # o dia que fecha é o dia local (mesma fronteira usada por agregar_dia())
    scheduler = BackgroundScheduler(timezone=TZ_LOCAL)
    scheduler.add_job(
        agregar_pendentes,
        CronTrigger(hour=0, minute=5, timezone=TZ_LOCAL),
        misfire_grace_time=3600,
    )
    scheduler.start()

    print("Backend iniciado")
    # encerramento: código após yield roda quando a API desliga
    yield
    scheduler.shutdown()
    print("Backend encerrado")

app = FastAPI(
    title="Lumen — Iluminação Inteligente",
    lifespan=lifespan
)

# O frontend roda em outra origem durante o desenvolvimento (Vite, porta 5173).
# A API e publica e nao usa cookies, portanto liberar as origens configuradas e seguro.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(comando.router)
app.include_router(estado.router)
app.include_router(eventos.router)
app.include_router(metricas.router)
