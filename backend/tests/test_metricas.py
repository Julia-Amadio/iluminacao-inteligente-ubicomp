"""
Testes do cálculo de métricas: atribuição por origem, fronteira de dia no fuso
local e varredura de dias pendentes.

Cada teste aqui existe por causa de uma regra que erraria em silêncio se
quebrasse — o resultado continuaria sendo um número plausível.
"""
from datetime import datetime, timedelta, timezone

import pytest

from config import TZ_LOCAL
from services import agregar_dia, agregar_pendentes


def evento(dia, hora, led, origem="sensor", minuto=0):
    """Evento com timestamp em UTC, como o backend grava."""
    return {
        "led": led,
        "origem": origem,
        "distancia": 10.0 if led == "on" else 200.0,
        "luminosidade": 500,
        "timestamp": datetime(2026, 7, dia, hora, minuto, tzinfo=timezone.utc),
    }


def dia_local(dia):
    """Meia-noite local do dia — o valor que agregar_dia grava em `data`."""
    return datetime(2026, 7, dia, tzinfo=TZ_LOCAL)


class TestAtribuicaoPorOrigem:
    """
    Só conta como economia o tempo apagado por decisão dos sensores. O tempo
    apagado por comando manual não é economia autônoma.
    """

    def test_tempo_apagado_manual_nao_conta_como_economia(self, db):
        # dia local 20 = 20/07 03:00Z -> 21/07 03:00Z
        db.eventos.insert_many([
            evento(20, 6, "on", "sensor"),    # apagado 03:00-06:00 = 3h (conta)
            evento(20, 10, "off", "manual"),  # apagado 10:00-14:00 por comando
            evento(20, 14, "off", "sensor"),  # apagado 14:00-18:00 = 4h (conta)
            evento(20, 18, "on", "sensor"),
        ])

        metrica = agregar_dia(datetime(2026, 7, 20))

        # 3h + 4h = 25200s. As 4h de apagado manual ficam de fora; contá-las
        # daria 39600s / 45.83%
        assert metrica["tempo_apagado_s"] == pytest.approx(25200, abs=1)
        assert metrica["percentual_economia"] == 29.17

    def test_manual_aceso_nao_infla_economia(self, db):
        """
        O atalho de simplesmente filtrar eventos manuais fora da consulta erraria
        aqui: sem o evento das 11h, a linha do tempo enxergaria o LED apagado o dia
        inteiro e reportaria 100% — quando ele esteve ACESO das 11h às 12h.
        """
        db.eventos.insert_many([
            evento(21, 11, "on", "manual"),
            evento(21, 12, "off", "sensor"),
        ])

        metrica = agregar_dia(datetime(2026, 7, 21))

        assert metrica["percentual_economia"] == 95.83
        assert metrica["percentual_economia"] < 100.0

    def test_evento_sem_campo_origem_e_tratado_como_sensor(self, db):
        """
        Documentos gravados antes de `origem` existir não têm o campo. Se a
        ausência não fosse lida como "sensor", as métricas de todo o histórico
        anterior iriam a zero.
        """
        db.eventos.insert_many([
            {"led": "on", "distancia": 10.0, "luminosidade": 500,
             "timestamp": datetime(2026, 7, 22, 6, tzinfo=timezone.utc)},
            {"led": "off", "distancia": 200.0, "luminosidade": 500,
             "timestamp": datetime(2026, 7, 22, 18, tzinfo=timezone.utc)},
        ])

        metrica = agregar_dia(datetime(2026, 7, 22))

        assert metrica["tempo_apagado_s"] > 0
        assert metrica["percentual_economia"] == 50.0


class TestFronteiraDeDiaLocal:
    """
    O dia é uma janela de 24h que começa à meia-noite LOCAL, não à meia-noite UTC.
    A faixa 00:00-03:00 UTC é a única em que as duas convenções discordam.
    """

    def test_evento_na_faixa_ambigua_pertence_ao_dia_local_anterior(self, db):
        # 26/07 00:00Z e 01:30Z = 25/07 21:00 e 22:30 em Brasília
        db.eventos.insert_many([
            evento(26, 0, "on", minuto=0),
            evento(26, 1, "off", minuto=30),
        ])

        do_dia_25 = agregar_dia(datetime(2026, 7, 25))
        do_dia_26 = agregar_dia(datetime(2026, 7, 26))

        assert do_dia_25["total_eventos"] == 2, "eventos pertencem ao dia 25 local"
        assert do_dia_26["total_eventos"] == 0, "e não ao dia 26, como seria em UTC"

    def test_data_gravada_e_meia_noite_local(self, db):
        db.eventos.insert_one(evento(20, 12, "off"))

        metrica = agregar_dia(datetime(2026, 7, 20))

        assert metrica["data"] == dia_local(20)
        # meia-noite em Brasília é 03:00Z — é isso que distingue os documentos
        # gravados antes da adoção do fuso local, que usavam 00:00Z
        assert metrica["data"].astimezone(timezone.utc).hour == 3

    def test_data_civil_e_respeitada_independente_do_fuso_recebido(self, db):
        """
        `agregar_dia` usa ano/mês/dia do argumento e ignora o fuso dele. Se
        convertesse o instante, meia-noite UTC do dia 20 viraria 21h do dia 19 e a
        função agregaria o dia errado.
        """
        db.eventos.insert_one(evento(20, 12, "off"))

        por_utc = agregar_dia(datetime(2026, 7, 20, tzinfo=timezone.utc))
        por_local = agregar_dia(datetime(2026, 7, 20, tzinfo=TZ_LOCAL))
        ingenuo = agregar_dia(datetime(2026, 7, 20))

        assert por_utc["data"] == por_local["data"] == ingenuo["data"] == dia_local(20)

    def test_dia_comum_tem_86400_segundos(self, db):
        db.eventos.insert_one(evento(20, 12, "off"))

        metrica = agregar_dia(datetime(2026, 7, 21))

        assert metrica["percentual_economia"] == 100.0
        assert metrica["tempo_apagado_s"] == pytest.approx(86400, abs=1)

    @pytest.mark.parametrize("dia_dst, horas", [
        ((2026, 3, 8), 23),    # entrada do DST nos EUA: dia de 23h
        ((2026, 11, 1), 25),   # saída do DST: dia de 25h
    ])
    def test_dia_com_horario_de_verao_nao_usa_86400_fixo(self, db, monkeypatch,
                                                         dia_dst, horas):
        """
        `percentual_economia` divide pelo intervalo real entre as duas meia-noites
        locais, não por 86400. O Brasil aboliu o horário de verão em 2019, então
        com `America/Sao_Paulo` os dois cálculos coincidem sempre e a diferença é
        invisível — este teste usa um fuso que ainda tem DST para exercitá-la.

        Com divisor fixo, um dia de 23h totalmente apagado reportaria 95,83% em vez
        de 100%, e um de 25h reportaria 104,17%.
        """
        from zoneinfo import ZoneInfo

        import services

        monkeypatch.setattr(services, "TZ_LOCAL", ZoneInfo("America/New_York"))
        db.eventos.insert_one({
            "led": "off", "origem": "sensor", "distancia": 200.0, "luminosidade": 500,
            "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
        })

        metrica = agregar_dia(datetime(*dia_dst))

        assert metrica["tempo_apagado_s"] == pytest.approx(horas * 3600, abs=1)
        assert metrica["percentual_economia"] == 100.0


class TestAgregarPendentes:
    def test_agrega_so_dias_sem_metrica_e_ignora_o_dia_corrente(self, db, congelar_agora):
        congelar_agora(datetime(2026, 7, 25, 6, tzinfo=timezone.utc))
        db.eventos.insert_many([
            evento(20, 6, "on"), evento(20, 18, "off"),
            evento(21, 6, "on"), evento(21, 18, "off"),
            # dia 22 sem nenhum evento: ainda merece métrica, herdando o estado
            evento(23, 6, "on"), evento(23, 18, "off"),
            evento(25, 6, "on"),  # dia corrente
        ])
        db.metricas.insert_one({"data": dia_local(21), "total_eventos": -1,
                                "tempo_apagado_s": -1.0, "percentual_economia": -1.0})

        agregados = agregar_pendentes()

        dias = sorted(d.astimezone(TZ_LOCAL).day for d in agregados)
        assert dias == [20, 22, 23, 24], "o 21 já tinha métrica; o 25 é hoje"

        preservada = db.metricas.find_one({"data": dia_local(21)})
        assert preservada["total_eventos"] == -1, "métrica existente não é recalculada"
        assert db.metricas.find_one({"data": dia_local(25)}) is None

    def test_dia_sem_eventos_herda_o_estado_do_ultimo_evento_anterior(self, db, congelar_agora):
        """
        Um dia sem nenhuma transição (LED no mesmo estado das 00h às 24h) merece
        métrica igual — é por isso que a varredura percorre dia a dia em vez de
        perguntar ao banco quais dias têm evento.
        """
        congelar_agora(datetime(2026, 7, 23, 6, tzinfo=timezone.utc))
        db.eventos.insert_many([evento(21, 6, "on"), evento(21, 18, "off")])

        agregar_pendentes()

        vazio = db.metricas.find_one({"data": dia_local(22)})
        assert vazio is not None
        assert vazio["total_eventos"] == 0
        assert vazio["percentual_economia"] == 100.0

    def test_execucao_repetida_nao_duplica(self, db, congelar_agora):
        congelar_agora(datetime(2026, 7, 22, 6, tzinfo=timezone.utc))
        db.eventos.insert_many([evento(20, 6, "on"), evento(20, 18, "off")])

        agregar_pendentes()
        antes = db.metricas.count_documents({})
        assert agregar_pendentes() == []
        assert db.metricas.count_documents({}) == antes

    def test_banco_sem_eventos_nao_agrega_nada(self, db):
        assert agregar_pendentes() == []


class TestEstadoCorrente:
    """
    O modo de operação é derivado: o timer do override roda no ESP32, e o backend
    reproduz a contagem para o caso de a placa cair antes de avisar que voltou ao
    automático.
    """

    def _inserir_manual(self, db, segundos_atras):
        agora = datetime.now(timezone.utc)
        db.eventos.insert_one({
            "led": "off", "origem": "manual", "distancia": None, "luminosidade": 500,
            "timestamp": agora - timedelta(seconds=segundos_atras),
        })

    def test_override_recente_reporta_modo_manual(self, db):
        from config import OVERRIDE_MANUAL_SEGUNDOS
        from services import estado_corrente

        self._inserir_manual(db, OVERRIDE_MANUAL_SEGUNDOS // 2)

        estado = estado_corrente()

        assert estado["modo"] == "manual"
        assert estado["override_expira_em"] is not None

    def test_override_vencido_volta_a_automatico(self, db):
        from config import OVERRIDE_MANUAL_SEGUNDOS
        from services import estado_corrente

        self._inserir_manual(db, OVERRIDE_MANUAL_SEGUNDOS * 2 + 1)

        estado = estado_corrente()

        assert estado["modo"] == "automatico"
        assert estado["override_expira_em"] is None
        assert estado["origem"] == "manual", "a origem do evento é preservada"

    def test_banco_vazio_nao_estoura(self, db):
        from services import estado_corrente

        estado = estado_corrente()

        assert estado["led"] is None
        assert estado["modo"] == "automatico"
