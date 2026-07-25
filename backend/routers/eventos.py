# backend/routers/eventos.py
from fastapi import APIRouter
from pymongo import ASCENDING
from datetime import datetime
from config import TZ_LOCAL
from database import db

router = APIRouter(prefix="/eventos", tags=["eventos"])

@router.get("")
def get_eventos(limite: int = 50):
    """
    Retorna os eventos mais recentes.
    Usado pela visualização de histórico no frontend.
    """
    eventos = list(
        db.eventos
        .find({}, {"_id": 0}) # exclui _id do retorno
        .sort("timestamp", -1)
        .limit(limite)
    )
    return eventos

@router.get("/hoje")
def get_eventos_hoje():
    """
    Retorna todos os eventos do dia atual, com a fronteira do dia no fuso local
    (`TZ_LOCAL`) — mesma fronteira usada pelas agregações, para que "hoje" aqui e
    "hoje" nas métricas signifiquem o mesmo dia.
    """
    inicio = datetime.now(TZ_LOCAL).replace(hour=0, minute=0, second=0, microsecond=0)
    eventos = list(
        db.eventos
        .find({"timestamp": {"$gte": inicio}}, {"_id": 0})
        .sort("timestamp", ASCENDING)
    )
    return eventos
