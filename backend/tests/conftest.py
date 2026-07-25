"""
Configuração comum dos testes.

Dois pontos que valem explicação:

- `MONGO_URI` é definida aqui antes de qualquer import dos módulos do backend.
  `config.py` a lê no import, e `database.py` constrói o MongoClient no import —
  construir não conecta (pymongo é preguiçoso), mas sem a variável a montagem
  ficaria dependente do ambiente de quem roda os testes.

- Nenhum teste toca MongoDB de verdade. A fixture `db` injeta um banco do
  `mongomock` nos módulos que importaram `db` de `database.py`. Como esses
  módulos fazem `from database import db`, o nome vive no namespace deles, e é lá
  que a substituição precisa acontecer.
"""
import os
import sys
from pathlib import Path

import pytest

# backend/ na frente do sys.path: os módulos usam imports absolutos entre si
# (config, database, services...), mesmo layout que o uvicorn e o Dockerfile usam
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/teste")

import mongomock  # noqa: E402


@pytest.fixture
def db(monkeypatch):
    """Banco em memória, já injetado em services e mqtt_client."""
    import mqtt_client
    import services

    banco = mongomock.MongoClient(tz_aware=True)["teste"]
    monkeypatch.setattr(services, "db", banco)
    monkeypatch.setattr(mqtt_client, "db", banco)
    return banco


@pytest.fixture
def congelar_agora(monkeypatch):
    """
    Fixa o "agora" visto por services.py.

    Recebe um datetime aware e devolve um substituto de `datetime` cujo `now(tz)`
    responde sempre aquele instante, convertido para o fuso pedido — respeitar o
    argumento `tz` importa porque o código chama tanto `now(TZ_LOCAL)` quanto
    `now(timezone.utc)`, e um stub que ignorasse isso mascararia erros de fuso.
    """
    from datetime import datetime

    def aplicar(instante):
        class AgoraFixo(datetime):
            @classmethod
            def now(cls, tz=None):
                return instante if tz is None else instante.astimezone(tz)

        import services

        monkeypatch.setattr(services, "datetime", AgoraFixo)
        return instante

    return aplicar
