# backend/routers/comando.py
# Endpoint de atuação remota: recebe um comando por HTTP e o repassa ao ESP32
# pelo tópico MQTT de controle. É o caminho que faz o backend mediar os dois
# sentidos da comunicação, e não só ingerir eventos.
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import MQTT_TOPICO_CONTROLE, OVERRIDE_MANUAL_SEGUNDOS
from mqtt_client import publicar_comando

router = APIRouter(prefix="/comando", tags=["comando"])

class Comando(BaseModel):
    # Literal em vez de str: o Pydantic rejeita qualquer outro valor com 422 antes
    # de chegar no handler, e o Swagger em /docs já mostra as opções válidas.
    led: Literal["on", "off"]

@router.post("")
def post_comando(comando: Comando):
    """
    Envia um comando manual de acionamento para o ESP32.

    O comando sobrepõe a decisão da fusão de contexto (sensores) por
    `override_segundos`, e depois o ESP32 volta sozinho ao modo automático.

    **Importante:** a resposta confirma que o comando foi publicado no broker, não
    que o ESP32 recebeu ou atuou — a placa pode estar desligada ou sem Wi-Fi. A
    confirmação de que a atuação aconteceu é o evento com `origem: "manual"` que o
    ESP32 publica de volta, visível em `GET /eventos` e `GET /estado`.

    Este endpoint não substitui o caminho do frontend, que publica no mesmo tópico
    direto por WebSocket — os dois convergem no mesmo lugar.
    """
    if not publicar_comando(comando.led):
        raise HTTPException(
            status_code=503,
            detail="Não foi possível publicar o comando no broker MQTT.",
        )

    return {
        "status"           : "publicado",
        "led"              : comando.led,
        "topico"           : MQTT_TOPICO_CONTROLE,
        "override_segundos": OVERRIDE_MANUAL_SEGUNDOS,
    }
