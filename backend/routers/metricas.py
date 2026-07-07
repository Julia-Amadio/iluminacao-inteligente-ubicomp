# backend/routers/metricas.py
from fastapi import APIRouter
from database import db
from services import agregar_dia

router = APIRouter(prefix="/metricas", tags=["metricas"])

@router.get("")
def get_metricas(limite: int = 30):
    """
    Retorna as métricas diárias agregadas mais recentes.
    Usado pelo painel de eficiência energética no frontend.
    """
    metricas = list(
        db.metricas
        .find({}, {"_id": 0})
        .sort("data", -1)
        .limit(limite)
    )
    return metricas

@router.post("/agregar")
def endpoint_agregar():
    """
    Dispara manualmente a agregação do dia anterior.
    Durante os testes substitui um job automático.
    """
    resultado = agregar_dia()
    if resultado is None:
        return {"status": "sem eventos para agregar"}
    return {"status": "ok", "metrica": resultado}
