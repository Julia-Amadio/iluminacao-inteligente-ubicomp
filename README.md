# iluminacao-inteligente-ubicomp
Desenvolvimento de um sistema embarcado distribuído de iluminação inteligente usando ESP32. Projeto final para a disciplina de Computação Pervasiva e Ubíqua (1º Semestre de 2026).

## Rodar (API)
```
cd backend
python -m venv venv

# Linux/Mac
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn main:app --reload
```
A documentação automática da API fica disponível em `http://localhost:8000/docs` assim que o servidor sobe.

A `.env` (não versionada) guarda a connection string do MongoDB e, opcionalmente, as configs do broker MQTT — variáveis detalhadas em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#27-configuração-env). MongoDB Atlas tem tier gratuito que serve bem; uma observação: no Atlas precisamos liberar o IP de acesso, em desenvolvimento colocar `0.0.0.0/0` para não travar durante os testes.

## Documentação

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitetura do sistema completo (os quatro protótipos) e detalhamento da API (estrutura de pastas, modelo de concorrência, fluxo de dados, modelo de dados no MongoDB, endpoints).
- [`docs/1_PLANEJAMENTO.pdf`](docs/1_PLANEJAMENTO.pdf) — planejamento e proposta original do projeto.
- [`docs/2_RELATÓRIO_PROTO2.pdf`](docs/2_RELATÓRIO_PROTO2.pdf) — relatório de execução dos Protótipos 1 e 2 (montagem física e testes com o broker MQTT).

## Roadmap

Protótipos 1 e 2 (ESP32: sensoriamento, fusão de contexto, publicação MQTT) já estão implementados
e documentados no relatório. O que falta está dividido abaixo — ver
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#3-limitações-conhecidas-e-próximos-passos)
para o raciocínio por trás de cada item.

### Protótipo 3 — Gateway computacional e persistência

Já implementado: subscriber MQTT, fila + worker de inserção, TTL nos eventos, `agregar_dia()`,
endpoints `/eventos` e `/metricas`. Falta:

- [ ] Validar o payload recebido do ESP32 antes de inserir (hoje `_inserir_evento` confia cegamente
      em `payload.get(...)`; um payload malformado insere campos `None` silenciosamente)
- [ ] Agendar `agregar_dia()` automaticamente (APScheduler ou cron), substituindo o
      `POST /metricas/agregar` manual usado nos testes
- [ ] Criar `.env.example` com as variáveis documentadas em `docs/ARCHITECTURE.md`
- [ ] Fixar versões em `requirements.txt` (`paho-mqtt==2.1.0`, etc.)
- [ ] Testes automatizados mínimos (endpoints e `agregar_dia()`, incluindo os casos de borda de
      início/fim de dia)

### Protótipo 4 — Interface e atuação remota bidirecional

Ainda não iniciado. Divisão sugerida:

**Preparação do backend/dados**
- [ ] Adicionar campo de origem no schema de eventos (ex. `"origem": "sensor" | "manual"`) — a métrica
      de eficiência energética precisa parar de contar como "economia autônoma" o tempo em que o LED
      ficou apagado por comando manual
- [ ] Atualizar `agregar_dia()` para considerar apenas `origem: "sensor"` no cálculo de
      `tempo_apagado_s`

**Firmware ESP32**
- [ ] Assinar um tópico de controle além de publicar no tópico de eventos
- [ ] Implementar a lógica de override: comando manual recebido sobrepõe a decisão da fusão de
      contexto (sensores) até novo comando ou critério de expiração
- [ ] Publicar o evento de transição resultante com `origem: "manual"` quando disparado por comando

**Frontend React**
- [ ] Setup do projeto e cliente MQTT (via WebSockets) para publicar no tópico de controle
      diretamente do navegador
- [ ] Tela de histórico de eventos, consumindo `GET /eventos`
- [ ] Painel de eficiência energética, consumindo `GET /metricas`
- [ ] Controle manual do LED (liga/desliga), publicando no tópico de controle
- [ ] Build e hospedagem (definir onde o frontend vai rodar)
