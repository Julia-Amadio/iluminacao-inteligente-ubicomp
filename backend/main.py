# backend/main.py
# Instancia FastAPI
# Importa de tudo. Monta o lifespan, registra os routers com app.include_router(), 
# e é o único arquivo que o uvicorn precisa conhecer.
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import inicializar_banco
from mqtt_client import iniciar_subscriber, worker_insercao
from routers import eventos, metricas

@asynccontextmanager
async def lifespan(app: FastAPI):
    # inicialização: roda antes de aceitar requisições
    inicializar_banco()

    # subscriber MQTT. daemon=True garante que morre junto com o processo principal
    threading.Thread(target=iniciar_subscriber, daemon=True).start()

    # worker de inserção no Mongo, consome fila_eventos
    threading.Thread(target=worker_insercao, daemon=True).start()

    print("Backend iniciado")
    # encerramento: código após yield roda quando a API desliga
    yield
    print("Backend encerrado")

app = FastAPI(
    title="Iluminação Inteligente — Grupo 1",
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

app.include_router(eventos.router)
app.include_router(metricas.router)
