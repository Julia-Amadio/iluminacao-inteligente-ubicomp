"""
Testes da ingestão de eventos, do endpoint de atuação remota e da consistência
entre a janela de override do backend e a do firmware.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import mqtt_client
from config import MQTT_TOPICO_CONTROLE, OVERRIDE_MANUAL_SEGUNDOS
from routers import comando as router_comando


class TestIngestaoDeEventos:
    def test_grava_origem_e_usa_sensor_como_padrao(self, db):
        mqtt_client._inserir_evento({"led": "on", "distancia": 12.0, "luminosidade": 500})
        mqtt_client._inserir_evento({"led": "off", "origem": "manual",
                                     "distancia": None, "luminosidade": 800})

        gravados = list(db.eventos.find({}, {"_id": 0}).sort("timestamp", 1))

        assert [e["origem"] for e in gravados] == ["sensor", "manual"]

    @pytest.mark.parametrize("payload", [
        {"led": "ligado"},          # valor fora do domínio
        {"led": "ON"},              # maiúsculas
        {"origem": "manual"},       # sem o campo led
        {"led": None},
    ])
    def test_descarta_payload_com_led_invalido(self, db, payload):
        """
        `led` é o único campo que não pode ser aceito às cegas: `distancia` e
        `luminosidade` são nuláveis por natureza (o HC-SR04 devolve None fora de
        alcance), mas um `led` inválido nunca casaria com "off" na linha do tempo
        de `agregar_dia()` e falsearia o tempo apagado sem sinal de erro.
        """
        mqtt_client._inserir_evento(payload)

        assert db.eventos.count_documents({}) == 0

    def test_timestamp_e_anexado_pelo_backend_em_utc(self, db):
        """
        O ESP32 não tem RTC confiável sem NTP, então o instante de recepção é a
        fonte de verdade — e instantes ficam sempre em UTC.
        """
        mqtt_client._inserir_evento({"led": "on", "distancia": 12.0, "luminosidade": 500})

        gravado = db.eventos.find_one({}, {"_id": 0})

        assert gravado["timestamp"].tzinfo is not None
        assert gravado["timestamp"].utcoffset().total_seconds() == 0


class TestEndpointDeComando:
    def test_aceita_apenas_on_e_off(self):
        assert router_comando.Comando(led="on").led == "on"
        assert router_comando.Comando(led="off").led == "off"

        for invalido in ("ligado", "ON", "", "1"):
            with pytest.raises(ValidationError):
                router_comando.Comando(led=invalido)

    def test_publica_e_informa_a_janela_do_override(self, monkeypatch):
        publicados = []
        monkeypatch.setattr(router_comando, "publicar_comando",
                            lambda led: publicados.append(led) or True)

        resposta = router_comando.post_comando(router_comando.Comando(led="on"))

        assert publicados == ["on"]
        assert resposta["status"] == "publicado"
        assert resposta["topico"] == MQTT_TOPICO_CONTROLE
        assert resposta["override_segundos"] == OVERRIDE_MANUAL_SEGUNDOS

    def test_falha_na_publicacao_vira_503(self, monkeypatch):
        monkeypatch.setattr(router_comando, "publicar_comando", lambda led: False)

        with pytest.raises(HTTPException) as erro:
            router_comando.post_comando(router_comando.Comando(led="off"))

        assert erro.value.status_code == 503

    def test_payload_publicado_fixa_origem_manual(self, monkeypatch):
        """
        A origem é fixada pelo backend, não lida de quem chamou: é o que impede
        marcar um comando manual como "sensor" e falsear a economia autônoma.
        """
        enviados = []
        monkeypatch.setattr(mqtt_client.cliente_mqtt, "publish",
                            lambda topico, payload, qos=0: enviados.append((topico, payload))
                            or type("R", (), {"rc": 0})())

        assert mqtt_client.publicar_comando("off") is True

        topico, payload = enviados[0]
        assert topico == MQTT_TOPICO_CONTROLE
        assert json.loads(payload) == {"led": "off", "origem": "manual"}


class TestConsistenciaComOFirmware:
    def test_janela_de_override_igual_no_backend_e_no_firmware(self):
        """
        O timer real roda no ESP32; o backend reproduz a contagem para informar o
        modo em GET /estado. Se os dois valores divergirem, a API e a placa passam a
        discordar sobre quando o override terminou — sem erro nenhum aparecer.
        """
        firmware = Path(__file__).resolve().parents[2] / "docs" / "codigo_esp32.py"
        if not firmware.exists():
            pytest.skip("firmware não encontrado em docs/codigo_esp32.py")

        linha = next(
            (l for l in firmware.read_text(encoding="utf-8").splitlines()
             if l.strip().startswith("OVERRIDE_MANUAL_MS")),
            None,
        )
        assert linha is not None, "OVERRIDE_MANUAL_MS não encontrado no firmware"

        expressao = linha.split("=", 1)[1].split("#")[0].strip()
        ms_firmware = eval(expressao, {"__builtins__": {}})  # noqa: S307 - literal do próprio repo

        assert ms_firmware == OVERRIDE_MANUAL_SEGUNDOS * 1000, (
            f"firmware usa {ms_firmware}ms e backend usa "
            f"{OVERRIDE_MANUAL_SEGUNDOS * 1000}ms"
        )
