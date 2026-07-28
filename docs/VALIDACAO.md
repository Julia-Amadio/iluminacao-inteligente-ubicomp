# Registro de validação

O que foi efetivamente exercitado no hardware e no sistema rodando, com as evidências observadas.
Este documento existe para separar **o que está comprovado** do **que está apenas implementado** — a
distinção que importa na hora de afirmar qualquer coisa no relatório ou na apresentação.

O raciocínio de projeto por trás de cada decisão está em [`ARCHITECTURE.md`](./ARCHITECTURE.md); aqui
ficam só os fatos observados.

## 1. Validado com evidência

### 1.1. Ambiente de desenvolvimento embarcado — 2026-07-22

Bring-up completo do ESP32 numa máquina que nunca havia rodado nada embarcado: driver CH9102, Thonny,
firmware MicroPython e REPL. Roteiro e evidências em [`SETUP_EMBARCADOS.md`](./SETUP_EMBARCADOS.md).

### 1.2. Protótipo 3 — persistência e agregação — 2026-07-21

Eventos publicados pelo ESP32 chegando ao MongoDB e `agregar_dia()` produzindo métrica corretamente.

### 1.3. Protótipo 4 — caminho de sensor com `origem` — 2026-07-25

Firmware atualizado publicando o campo `origem`, e backend persistindo-o.

Log do Thonny:

```
>> Transição: off/sensor -> on/sensor
Publicado: {"led": "on", "luminosidade": 550, "origem": "sensor", "distancia": 3.67241368}
>> Transição: on/sensor -> off/sensor
Publicado: {"led": "off", "luminosidade": 807, "origem": "sensor", "distancia": 107.74138}
```

Log do backend (em container), mesmos eventos:

```
Evento inserido: {'led': 'on', 'distancia': 3.67241368, 'luminosidade': 550, 'origem': 'sensor',
                  'timestamp': datetime(2026, 7, 25, 4, 56, 45, ...)}
Evento inserido: {'led': 'off', 'distancia': 107.74138, 'luminosidade': 807, 'origem': 'sensor',
                  'timestamp': datetime(2026, 7, 25, 4, 56, 46, ...)}
```

Confirma também a fusão de contexto: 3,67 cm + 550 (presença e escuro) → `on`; 107 cm + 807 (sem
presença) → `off`.

### 1.4. Protótipo 4 — atuação remota, publicação direta no tópico de controle — 2026-07-25

Comando publicado no tópico de controle por um cliente externo, com um observador independente
assinando o tópico de eventos:

```
t+3.2s   publicado {"led":"on","origem":"manual"} em pervasiva/grupo1/iluminacao/controle
t+4.0s   EVENTO <- led=on   origem=manual   dist=160.16cm  lum=509
t+14.8s  EVENTO <- led=off  origem=sensor   dist=160.50cm  lum=559
```

Três fatos nesse trace:

- **o override realmente sobrepõe os sensores** — a 160 cm não há presença, então a fusão de contexto
  pedia `off`, e o LED acendeu de todo modo;
- **latência de ~0,8 s** entre comando e evento de resposta (o `check_msg()` a cada 100 ms);
- **a expiração funciona e devolve o controle** — ~10,8 s após o comando (janela de 10 s + até 1 s para
  o próximo ciclo de sensor notar), voltando a `origem: "sensor"`.

### 1.5. Protótipo 4 — atuação remota via `POST /comando` — 2026-07-25

Mesmo teste, agora exercitando o endpoint da API. O subscriber rodou em thread daemon (como no
`lifespan`) e a publicação partiu da thread principal, reproduzindo o cenário real do handler HTTP:

```
t+0.7s   publicar_comando('on') da thread principal -> True
t+1.7s   EVENTO <- led=on   origem=manual   dist=160.48cm
t+12.5s  EVENTO <- led=off  origem=sensor   dist=160.41cm
         fila_eventos do backend: 2 eventos ingeridos
```

O ponto adicional aqui: o **mesmo** cliente paho compartilhado publicou o comando (thread HTTP) e
recebeu os eventos de volta (thread do subscriber), numa única conexão — a premissa de thread-safety
descrita em `ARCHITECTURE.md` seção 2.6 confirmada na prática.

### 1.6. Protótipo 4 — atuação pelo Swagger (`/docs`) — 2026-07-25

Teste manual pelo Swagger, com o ESP32 rodando:

- `{"led": "off"}` **apaga** o LED mesmo com a condição de presença satisfeita;
- `{"led": "on"}` **acende** o LED mesmo sem presença.

É a validação mais direta do override: a atuação remota vence a decisão autônoma nos dois sentidos.

### 1.7. Migração para fronteira de dia local, contra o Atlas real — 2026-07-25

Após esvaziar a coleção `metricas` (e **não** `eventos`) e reiniciar a API, `agregar_pendentes()`
reconstruiu tudo do zero no startup, já com a fronteira local:

```
Índices inicializados
Métrica agregada para 2026-07-21 : {'data': datetime(2026,7,21,0,0, tzinfo=ZoneInfo('America/Sao_Paulo')),
                                    'total_eventos': 4, 'tempo_apagado_s': 44268.634999, 'percentual_economia': 51.24}
Métrica agregada para 2026-07-22 : {... 'total_eventos': 4, 'tempo_apagado_s': 57590.707999, 'percentual_economia': 66.66}
Métrica agregada para 2026-07-23 : {... 'total_eventos': 2, 'tempo_apagado_s': 61198.927999, 'percentual_economia': 70.83}
Métrica agregada para 2026-07-24 : {... 'total_eventos': 6, 'tempo_apagado_s': 50394.489999, 'percentual_economia': 58.33}
Dias pendentes agregados: ['2026-07-21', '2026-07-22', '2026-07-23', '2026-07-24']
```

Isso valida quatro coisas de uma vez:

- **`agregar_pendentes()` contra a base real**, reconstruindo dias sem métrica — até então só havia
  sido exercitado com dados sintéticos;
- **a migração sem documentos duplicados**, confirmando que o wipe da `metricas` era o passo suficiente;
- **o dia corrente sendo excluído**: o dataset tem 10 eventos no dia 25, e nenhuma métrica foi gravada
  para ele. Se fosse agregado, daria 99,99% — exatamente a métrica parcial e enganosa que o guard
  `dia < hoje` existe para evitar;
- **a agregação em si**, por conferência independente: rodar `agregar_dia()` fora da API, sobre um dump
  da coleção `eventos` exportado do Atlas, reproduz `tempo_apagado_s` e `percentual_economia`
  idênticos aos quatro valores acima, até a terceira casa decimal. (O dump era temporário e não está
  versionado.)

Esta primeira reconstrução, porém, **não** provava que a fronteira local estava em uso. A versão do
dataset usada aqui não tinha nenhum evento entre 00:00 e 03:00 UTC, e a janela local é a UTC deslocada
em +3 h: ela exclui essa faixa do próprio dia e inclui a do dia seguinte. Sem eventos em nenhuma das
duas, ambas ficavam integralmente `off` e se cancelavam, produzindo percentuais iguais nas duas
convenções. A prova veio depois — ver 1.8.

### 1.8. Fronteira de dia local, comprovada na faixa ambígua — 2026-07-25

Para distinguir as duas convenções é preciso LED **aceso** dentro da faixa 00:00–03:00 UTC, que é
21:00–00:00 do dia anterior em Brasília. Dois eventos foram inseridos no dataset:

```
2026-07-24T00:03:54Z  led=on
2026-07-24T02:03:55Z  led=off      → 2 h de LED aceso, 23/07 21:03–23:03 BRT
```

Após novo wipe da `metricas` e reinício, a API gravou para o dia 23
`total_eventos: 4, tempo_apagado_s: 53997.852, percentual_economia: 62.5` — antes era
`2, 61198.928, 70.83`.

Agregando o mesmo dataset nas duas convenções:

| dia | % com fronteira local | % com fronteira UTC | difere |
|---|---|---|---|
| 2026-07-21 | 51,24 % | 51,24 % | não |
| 2026-07-22 | 66,66 % | 66,66 % | não |
| **2026-07-23** | **62,50 %** | 70,83 % | **sim** |
| **2026-07-24** | **58,33 %** | 49,99 % | **sim** |

O Atlas contém 62,50 % e 58,33 %, ou seja a coluna local — se o sistema ainda usasse fronteira UTC,
teria gravado 70,83 % e 49,99 %.

A conta fecha exatamente: as 2 h de LED aceso **migraram** de dia. O dia 23 perdeu 8,33 pontos
percentuais (7200 s = 2 h) e o dia 24 ganhou os mesmos 8,33 pontos. Nada foi criado nem perdido — o
tempo apenas passou a ser contado no dia em que aconteceu segundo o horário de Brasília. Os eventos
inseridos moram no dia 24 do calendário UTC e no dia 23 do calendário local, e é essa discordância que
a mudança resolve.

## 2. Implementado mas **não** validado

Nada aqui está sabidamente quebrado — só não foi exercitado, e portanto não deve ser afirmado como
comprovado.

| Item | Situação |
|---|---|
| Janela de override de **300 s** (valor de entrega) | Só a janela de teste de 10 s foi exercitada. A lógica é a mesma, mas o valor de produção nunca rodou. Ver o aviso em `backend/config.py`. Há teste garantindo que firmware e backend usam o mesmo valor, qualquer que seja ele. |
| Comportamento em transição de horário de verão | Coberto por teste (dias de 23 h e 25 h, usando um fuso que ainda tem HV), mas o Brasil não tem HV desde 2019 — nunca ocorreu em operação real. |
| Atribuição por origem em um dia real | Validada com linhas do tempo sintéticas, incluindo o caso em que filtrar eventos manuais superestimaria a economia. Nenhum dia real com override foi agregado ainda: todos os 26 eventos do dataset têm `origem: "sensor"`. |
| `reconectar()` no firmware | Escrito para reassinar o tópico de controle após queda de conexão — cenário nunca provocado. Exercitar exigiria derrubar o Wi-Fi ou o broker durante a operação. |
| Frontend em execução contra API/broker reais | O build e o lint passam, e a integração está implementada (`/eventos`, `/eventos/hoje`, `/metricas`, `/estado`, origem no histórico e comandos MQTT). Ainda falta abrir o painel com o sistema físico completo e registrar evidência visual/funcional. |
| Job diário disparando às 00:05 locais | O `CronTrigger` foi confirmado calculando o próximo disparo em 00:05 local (= 03:05 UTC), mas nunca foi observado efetivamente disparar. |

### 2.1. Validação estática do frontend — 2026-07-27

Executados com sucesso:

```text
npm run build  → TypeScript + Vite, 38 módulos transformados
npm run lint   → ESLint sem erros
```

Também foi removida a série fictícia exibida quando não havia métricas. O estado vazio agora é
explícito, e os cartões usam os endpoints do backend para modo de operação e eventos do dia.

## 3. Pontos que rendem discussão na apresentação

Todos estão desenvolvidos em [`ARCHITECTURE.md`](./ARCHITECTURE.md) — a lista serve para localizá-los.

1. **Por que a métrica não pode simplesmente descartar os eventos manuais** (seção 2.5). O atalho
   óbvio corrompe a linha do tempo: um comando manual de *acender* descartado faz o cálculo enxergar o
   LED apagado e **superestimar** a economia. A solução é ler todos os eventos e usar a origem apenas
   como critério de contagem.
2. **Dois relógios medindo a mesma janela** (seção 2.6). O timer do override roda no ESP32, mas o
   backend precisa reproduzi-lo para informar o modo atual — porque se a placa cair durante o
   override, o evento de volta nunca chega e o último evento no banco ficaria "manual" para sempre.
3. **Publicar por mudança do par (estado, origem)** (seção 1.3), e não só do estado. Um comando que
   pede o estado em que o LED já está não altera `led`, mas altera quem decide — e sem esse evento o
   backend não saberia que um override começou.
4. **Um dia silencioso é ambíguo** (seção 3). Como o ESP32 só publica em transição, um dia sem eventos
   pode significar economia real ou placa desligada, e a coleção não distingue. A correção adequada é
   um heartbeat, fora do escopo atual.
5. **Ordem entre agregação e TTL** (seções 2.5 e 3). A métrica só é calculável enquanto os eventos
   brutos existirem; passados 7 dias, um dia sem métrica é definitivamente irrecuperável.
6. **APScheduler no processo, não cron do sistema operacional** (seção 2.5), mantendo a decisão de
   processo único com threads daemon da seção 2.3.
7. **Instante em UTC, fronteira de dia em local** (seção 2.5). São problemas distintos: guardar
   *quando* algo aconteceu é UTC; decidir *a que dia* pertence tem de ser local, senão a "economia
   diária" mede um dia deslocado em três horas em relação ao dia das pessoas.
