# iluminacao-inteligente-ubicomp
Desenvolvimento de um sistema embarcado distribuído de iluminação inteligente usando ESP32. Projeto final para a disciplina de Computação Pervasiva e Ubíqua (1º Semestre de 2026).

---

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

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Não precisam de MongoDB nem de broker: o banco é substituído por `mongomock` e o cliente MQTT é
stubado. A suíte é curta de propósito — cobre as regras que errariam **em silêncio**, produzindo um
número plausível em vez de um erro: atribuição de economia por origem do evento, fronteira de dia no
fuso local, exclusão do dia corrente na agregação, compatibilidade com eventos gravados antes do campo
`origem`, e a consistência entre a janela de override do backend e a do firmware.

## Rodar (Docker)

O `Dockerfile` fica na raiz do repositório (não em `backend/`), então os comandos abaixo rodam
a partir daqui. Precisa de um `.env` na raiz com pelo menos `MONGO_URI` (ver `.env.example`).

```
docker build -t iluminacao-inteligente .
docker run --rm -p 8000:8000 --env-file .env iluminacao-inteligente
```

A API sobe em `http://localhost:8000`, com o mesmo Swagger em `/docs`. Não use aspas nos valores
do `.env` — o `python-dotenv` (execução local) as remove sozinho, mas `docker run --env-file` não,
e a URI do Mongo quebra com aspas literais.

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

O `.env` (não versionado, na raiz do repositório — mesmo lugar do `.env.example` e do `Dockerfile`) guarda a connection string do MongoDB e, opcionalmente, as configs do broker MQTT — variáveis detalhadas em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#27-configuração-env). No Atlas o IP de acesso está como `0.0.0.0/0` para não travar durante os testes.

---

## Documentação

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitetura do sistema completo (os quatro protótipos) e detalhamento da API (estrutura de pastas, modelo de concorrência, fluxo de dados, modelo de dados no MongoDB, endpoints).
- [`docs/VALIDACAO.md`](docs/VALIDACAO.md) — registro do que foi efetivamente validado no hardware, com as evidências observadas, e do que está implementado mas ainda não exercitado. Inclui os pontos de projeto que rendem discussão na apresentação.
- [`docs/SETUP_EMBARCADOS.md`](docs/SETUP_EMBARCADOS.md) — roteiro de bring-up do ambiente embarcado (driver CH9102, Thonny, firmware MicroPython) numa máquina do zero.
- [`docs/codigo_esp32.py`](docs/codigo_esp32.py) — firmware MicroPython do ESP32 (sensoriamento, fusão de contexto, publicação MQTT e override manual).
- [`docs/1_PLANEJAMENTO.pdf`](docs/1_PLANEJAMENTO.pdf) — planejamento e proposta original do projeto.
- [`docs/2_RELATÓRIO_PROTO2.pdf`](docs/2_RELATÓRIO_PROTO2.pdf) — relatório de execução dos Protótipos 1 e 2 (montagem física e testes com o broker MQTT).

---

## Roadmap

Protótipos 1 e 2 (ESP32: sensoriamento, fusão de contexto, publicação MQTT) já estão implementados
e documentados no relatório. O que falta está dividido abaixo — ver
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#3-limitações-conhecidas-e-próximos-passos)
para o raciocínio por trás de cada item.

### Protótipo 3 — Gateway computacional e persistência

Já implementado: subscriber MQTT, fila + worker de inserção, TTL nos eventos, `agregar_dia()`,
endpoints `/eventos` e `/metricas`. Falta:

- [x] Validar o payload recebido do ESP32 antes de inserir (hoje `_inserir_evento` confia cegamente
      em `payload.get(...)`; um payload malformado insere campos `None` silenciosamente)
- [x] Agendar `agregar_dia()` automaticamente (APScheduler ou cron), substituindo o
      `POST /metricas/agregar` manual usado nos testes — feito via `agregar_pendentes()`, que roda no
      startup e num job diário, e recupera dias sem métrica em vez de só agregar "ontem"
- [x] Criar `.env.example` com as variáveis documentadas em `docs/ARCHITECTURE.md`
- [x] Fixar versões em `requirements.txt` (`paho-mqtt==2.1.0`, etc.)
- [x] Testes automatizados mínimos (endpoints e `agregar_dia()`, incluindo os casos de borda de
      início/fim de dia) — em `backend/tests/`, sem dependência de Mongo ou broker

### Protótipo 4 — Interface e atuação remota bidirecional

O frontend React já está implementado com painel responsivo, histórico de eventos, leituras mais
recentes dos sensores, gráfico de eficiência energética e controle manual via MQTT. Para a atuação
remota funcionar de ponta a ponta, ainda faltam as alterações indicadas no backend e no firmware:

**Preparação do backend/dados**
- [x] Adicionar campo de origem no schema de eventos (ex. `"origem": "sensor" | "manual"`) — a métrica
      de eficiência energética precisa parar de contar como "economia autônoma" o tempo em que o LED
      ficou apagado por comando manual
- [x] Atualizar `agregar_dia()` para considerar apenas `origem: "sensor"` no cálculo de
      `tempo_apagado_s`
- [x] Expor `GET /estado` com o modo de operação (`automatico` | `manual`) — o frontend não consegue
      derivar isso de `/eventos` sozinho, porque o timer do override roda no ESP32 e pode expirar sem
      gerar evento novo
- [x] Expor `POST /comando` publicando no tópico de controle, para que a atuação remota também passe
      pelo gateway e fique testável pelo Swagger em `/docs`, sem depender do frontend

**Firmware ESP32** (código em [`docs/codigo_esp32.py`](docs/codigo_esp32.py) — validado no hardware, ver [`docs/VALIDACAO.md`](docs/VALIDACAO.md))
- [x] Assinar um tópico de controle além de publicar no tópico de eventos
- [x] Implementar a lógica de override: comando manual recebido sobrepõe a decisão da fusão de
      contexto (sensores) por 5 minutos, depois devolve o controle aos sensores
- [x] Publicar o evento de transição resultante com `origem: "manual"` quando disparado por comando
- [x] Testar no ESP32 físico: comando remoto acende com ausência de presença e apaga com presença
      detectada, e o override expira devolvendo o controle aos sensores
- [ ] Exercitar `reconectar()`: derrubar o Wi-Fi ou o broker durante a operação e confirmar que o
      ESP32 volta a receber comandos (a reinscrição no tópico nunca foi testada)

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
- [ ] Hospedagem (depende de publicar também a API e liberar sua origem no CORS;
      publicar apenas os arquivos estáticos deixaria o painel sem dados)

**Pendências encontradas na revisão do frontend**

- [x] O gráfico não fabrica dados: sem métricas, mostra um estado vazio explícito.
- [x] O indicador de modo consome `GET /estado` e alterna entre automático e manual.
- [x] "ECONOMIA MÉDIA" calcula a média do conjunto devolvido por `GET /metricas`; o rodapé do
      gráfico identifica separadamente o último registro.
- [x] "EVENTOS HOJE" consome `GET /eventos/hoje`, usando a mesma fronteira local das agregações.
- [x] Frontend validado com `npm run build` e `npm run lint`.
- [x] O histórico identifica cada transição como "Controle manual" ou "Automação por sensores".
