# backend/database.py
# Importa de config.py. Exporta a instância db que os demais usam.
# Faz conexão com mongo, inicializa banco e as duas coleções
from pymongo import MongoClient
from config import MONGO_URI

# Singleton. Criado uma vez aqui, importado pelos demais módulos
cliente_mongo = MongoClient(MONGO_URI)
db            = cliente_mongo["pervasiva_grupo1"]

def inicializar_banco():
    # idempotente: create_index não faz nada se o índice já existir
    # MongoDB cria as coleções automaticamente na primeira inserção,
    # mas os índices precisam ser criados explicitamente.
    
    # TTL index na coleção de eventos: deleta documentos após 7 dias
    db.eventos.create_index(
        "timestamp",
        expireAfterSeconds=604800  # TTL 7 dias
    )
    
    # índice comum em metricas para facilitar consultas por período
    db.metricas.create_index("data", unique=True)
    
    print("Índices inicializados")
