# backend/routers/estado.py
# Endpoint de estado corrente do sistema. Separado de eventos.py porque não
# devolve um evento: devolve o estado derivado da leitura mais recente, incluindo
# o modo de operação (automático ou override manual), que não existe como campo
# em nenhum documento do banco.
from fastapi import APIRouter
from services import estado_corrente

router = APIRouter(prefix="/estado", tags=["estado"])

@router.get("")
def get_estado():
    """
    Estado corrente do sistema: último estado do LED, leituras de sensor que o
    acompanharam, origem da transição e modo de operação.

    `modo` é "manual" enquanto um comando do dashboard ainda estiver valendo, e
    "automatico" quando a decisão está com a fusão de contexto do ESP32. Esse
    campo não pode ser derivado só de `GET /eventos`: se o override expirar sem
    mudar o estado do LED, o ESP32 não publica evento novo e o último evento
    permanece com `origem: "manual"` indefinidamente.

    `override_expira_em` vem preenchido apenas quando `modo == "manual"`.
    """
    return estado_corrente()
