# Setup de embarcados (ESP32 em casa)

Roteiro de bring-up do ambiente de desenvolvimento embarcado (ESP32 + MicroPython + Thonny) numa
máquina que nunca lidou com essa parte do projeto — feito em Windows nativo (não WSL, que não tem
acesso direto a portas seriais USB sem passthrough extra via `usbipd-win`).

Kit usado: ESP32 DevKit + adaptador de expansão + protoboard + cabo USB (mesmo kit dos
Protótipos 1 e 2, ver [`2_RELATÓRIO_PROTO2.pdf`](./2_RELATÓRIO_PROTO2.pdf)).

## 1. Identificar o chip USB-serial

Bloco preto perto do conector USB da placa, com o texto **CH9102x** — chip da fabricante WCH
(Nanjing Qinheng Microelectronics).

## 2. Driver USB-serial (CH9102) ✅

Chip CH9102 usa o pacote de driver unificado `CH343SER` da WCH, que cobre toda uma família de
chips (CH342/343/344/346/347, CH9101-9105, CH9111, CH9114, CH9143, CH9433) — não é um driver
dedicado só ao CH9102, mas o mesmo pacote serve.

- Fonte oficial: https://www.wch.cn/downloads/ch343ser_exe.html
- Baixado `CH343SER.EXE`, rodado o instalador (`DriverSetup(X64)`), `CH343SER.INF` selecionado
  automaticamente → clicado **INSTALL**.
- Após reconectar o cabo USB, o Device Manager passou a mostrar em "Portas (COM e LPT)":
  `USB-Enhanced-SERIAL CH9102 (COM3)`.

Driver confirmado funcionando — porta **COM3**.

## 3. Thonny — instalação da IDE ✅

Instalado via thonny.org (instalador Windows, standalone — não depende do Python do sistema).

## 4. Firmware MicroPython — flash via Thonny ✅

Módulo da placa: `ESP32-WROOM-32` (impresso na tampa metálica do chip principal).

`Run > Configure interpreter` → interpretador **MicroPython (ESP32)** → botão **"Install or update
firmware"**:

- Target port: `USB Single Serial @ COM3`
- `Erase all flash before installing` marcado
- MicroPython family: **ESP32**
- Variant: **Espressif • ESP32 / WROOM** (firmware genérico oficial da Espressif pro módulo
  WROOM — as outras opções da lista são variantes de fabricantes de placas específicas, ex.
  LILYGO, M5Stack, Olimex, SparkFun)

Flash concluído sem erros.

## 5. Teste de REPL / LED onboard ✅

Reconectado na COM3, prompt `>>>` do MicroPython apareceu no Shell do Thonny. Testado:

```python
import machine
led = machine.Pin(2, machine.Pin.OUT)
led.value(1)
```

LED azul onboard acendeu — confirma o ciclo completo PC ↔ driver CH9102 ↔ firmware MicroPython ↔
hardware fechado. Ambiente pronto para levar o código dos sensores (HC-SR04 + LDR) do Protótipo 2
pra essa bancada.
