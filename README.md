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

## Rodar (frontend)

```bash
cd frontend
npm install
npm run dev
```

O painel fica disponível em `http://localhost:5173`. As URLs da API e do broker MQTT WebSocket e o tópico de controle devem ser inseridos em `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_MQTT_URL=
VITE_MQTT_CONTROL_TOPIC=
```

As variáveis são opcionais durante o desenvolvimento, pois esses mesmos valores já são usados
como padrão pelo frontend. O painel consulta eventos e métricas da API ao abrir e atualiza os dados
a cada 30 segundos. A conexão MQTT usa WebSockets, requisito para acesso ao broker diretamente do
navegador.

A `backend/.env` (não versionada) guarda a connection string do MongoDB e, opcionalmente, as configs do broker MQTT — variáveis detalhadas em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#27-configuração-env). No Atlas o IP de acesso está como `0.0.0.0/0` para não travar durante os testes.

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

O frontend React já está implementado com painel responsivo, histórico de eventos, leituras mais
recentes dos sensores, gráfico de eficiência energética e controle manual via MQTT. Para a atuação
remota funcionar de ponta a ponta, ainda faltam as alterações indicadas no backend e no firmware:

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
- [x] Setup do projeto com React, TypeScript e Vite
- [x] Cliente MQTT via WebSockets para publicar no tópico de controle
      diretamente do navegador
- [x] Tela de histórico de eventos, consumindo `GET /eventos`
- [x] Painel de eficiência energética, consumindo `GET /metricas`
- [x] Controle manual do LED (liga/desliga), publicando comandos com `origem: "manual"` no tópico
      de controle
- [x] Atualização automática dos dados, feedback de conexão com a API e estado da conexão MQTT
- [x] Layout responsivo para desktop e dispositivos móveis
- [x] Build de produção com Vite (`npm run build`)
- [ ] Hospedagem (definir onde o frontend vai rodar)
