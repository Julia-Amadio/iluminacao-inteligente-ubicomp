# iluminacao-inteligente-ubicomp
Desenvolvimento de um sistema embarcado distribuído de iluminação inteligente usando ESP32. Projeto final para a disciplina de Computação Pervasiva e Ubíqua (1º Semestre de 2026).

## Rodar
```
pip install -r requirements.txt
uvicorn main:app --reload
```
A documentação automática da API fica disponível em `http://localhost:8000/docs` assim que o servidor sobe.

## Estrutura do projeto
```
backend/
├── main.py           # só a instância do FastAPI, lifespan e registro dos routers
├── config.py         # load_dotenv e todas as constantes
├── database.py       # conexão com Mongo, inicializar_banco(), as duas coleções
├── mqtt_client.py    # on_connect, on_message, iniciar_subscriber(), worker_insercao()
├── services.py       # agregar_dia() e qualquer outra regra de negócio de cálculo
├── routers/
│   ├── eventos.py    # endpoints /eventos e /eventos/hoje
│   └── metricas.py   # endpoints /metricas e /metricas/agregar
├── .env
└── requirements.txt
```

## MongoDB: instância e .env
MongoDB Atlas tem tier gratuito que serve bem. A `.env` guarda a connection string, lida com python-dotenv. Uma observação: no Atlas precisamos liberar o IP de acesso, em desenvolvimento colocar `0.0.0.0/0` para não travar durante os testes.

## Backend como subscriber + conversão JSON
O ESP32 já publica em JSON (o `ujson.dumps()` do Protótipo 2 cuida disso). O backend em Python recebe a string, faz `json.loads()` e já tem um dicionário pronto para inserir no Mongo. A biblioteca subscriber em Python é o `paho-mqtt`, que é o equivalente "adulto" do `umqtt.simple`.
```
paho-mqtt recebe mensagem → json.loads() → adiciona timestamp → insere no MongoDB
```
Timestamps não vem do ESP32 (ele não tem RTC confiável sem NTP). O backend anexa com `datetime.now()` no momento da recepção, o que é o correto para um sistema de log de eventos.

## FastAPI vs Flask
Para o que o Protótipo 4 precisa (alguns endpoints REST que o frontend consome), FastAPI é a escolha mais moderna (ao invés do Flask) e tem vantagens práticas: validação automática com Pydantic, documentação Swagger gerada automaticamente em `/docs` e suporte nativo a async que é útil se o subscriber MQTT e a API precisarem rodar no mesmo processo.

**Decisão importante:** o subscriber `paho-mqtt` e a API FastAPI precisarão rodar no mesmo processo ou em processos separados. A abordagem mais limpa é rodar o subscriber numa thread separada dentro do mesmo processo da API, com uma fila (`queue.Queue`) passando os eventos recebidos para o handler de inserção no Mongo.

## Timestamp e métricas
Para as métricas de eficiência energética (tempo que o LED ficou apagado autonomamente), uma função separada que agrega os documentos do Mongo por dia e calcula os intervalos entre eventos off e on é o caminho; não precisamos guardar a métrica calculada, só os eventos brutos, e calcula sob demanda no endpoint.

## Camada de eventos brutos — retenção curta
Os documentos individuais no Mongo (cada `{led, distancia, luminosidade, timestamp}`) só precisam existir pelo tempo necessário para calcular as métricas do período corrente. Para visualização no frontend, mostrar as últimas 24h ou no máximo 7 dias já é suficiente e evita que a coleção cresça indefinidamente. Dá para implementar com um TTL index no MongoDB, que deleta documentos automaticamente após um período configurável — uma linha na criação da coleção, sem precisar de nenhum job de limpeza.

## Camada de métricas agregadas — retenção longa
Aqui o dado não é mais o evento bruto, mas o resultado calculado: "no dia 07/07, o LED ficou apagado autonomamente por X horas, economizando Y% em relação a um cenário sem automação". Esse documento agregado é pequeno, não cresce na mesma proporção que os eventos, e faz sentido guardar por meses ou indefinidamente. Seria uma coleção separada no Mongo, populada por um job que roda uma vez por dia (ou sob demanda via endpoint) e agrega os eventos brutos do dia anterior antes que o TTL os delete.

## Implicação na arquitetura
Isso significa duas coleções distintas no Mongo com políticas de retenção diferentes, e dois tipos de endpoint na API:

- `/eventos`:consulta eventos recentes, usado pela visualização de histórico no frontend
- `/metricas`: consulta agregados por dia/semana/mês, usado pelo painel de eficiência energética

E um job de agregação rodando entre os dois, que pode ser tão simples quanto uma função chamada por um schedule Python ou um endpoint `/agregar` chamado manualmente durante os testes.

Três threads rodam simultaneamente: a thread principal é o servidor FastAPI; a segunda roda o `loop_forever()` do `paho-mqtt`, que fica bloqueada esperando mensagens; a terceira é o worker que consome a fila e escreve no Mongo. A `queue.Queue` é o ponto de comunicação entre a thread MQTT e a thread worker, isso evita que uma escrita lenta no Mongo atrase o recebimento de mensagens.

O endpoint `/metricas/agregar` substitui um job automático durante os testes — em produção isso seria um cron job ou um APScheduler chamando agregar_dia() toda meia-noite.
