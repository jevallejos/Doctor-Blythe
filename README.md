# HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0

* **Repositorio**: https://github.com/jevallejos/Doctor-Blythe.git
* **Arquitectura**: Micro-Kernel Hexagonal (45/45 Archivos Canonicos Certificados)
* **Exchange Objetivo**: Bybit Unified Trading Account (UTA V5) - Futuros Perpetuos USDT (25.0 Hz L2)
* **Entorno Productivo**: Python 3.11+ (`uvloop`, `ccxt.pro`) sobre Ubuntu Linux (`TCP BBR`, `fq`, `Nice=-10`, `OOM_Adj=-800`)

---

## 1. Dualidad Arquitectonica: Doctor Blythe (Defensa) + Terpsichora V7.0 (Ofensiva)

* **Doctor Blythe (Cirujano Reconstructor - Defensa Inmutable)**:
  Garantiza la supervivencia de la cuenta mediante el contrato estatico de 100 constantes (`AST_100_CONSTANTES_OK`), 18 escudos microestructurales no-regresivos (`SCAR-LOCK-00` a `SCAR-LOCK-18`), estado en RAM O(1) (`< 1.0 us`), paridad contable 1:1 con Bybit UTA y auditoria contrafactual a `+15.0s / +60.0s`.

* **Terpsichora V7.0 (Titiritera Ofensiva - Cosecha Maker)**:
  1. **Enganche de Fase (Phase-Latch 1800ms - 4500ms)**: Detecta dislocaciones extremas respecto a la `EMA900` y espera la confirmacion cinematica de frenado (Lyapunov + Hurst <= 0.485 + absorcion OFI/Hawkes) antes de disparar en `LONG` o `SHORT-SNIPER`.
  2. **Escudo Macro BTC (12.0s) con Liberacion Sincronizada**: Bloquea entradas durante sacudidas de Bitcoin y libera tempranamente el enfriamiento tras `3.5s` si BTC y la altcoin confirman un giro en V sincronizado.
  3. **Ejecucion 100% Maker (`PostOnly`) y Supervivencia en Cola**: Cotizacion Avellaneda-Stoikov, aborto prematuro de colas toxicas (`Early Queue Abort` a `0.80s`), captura anti-huerfanas de llenados en transito y filtro de lote minimo (`>= 15%`).
  4. **Gobernador de Salida Abraham Wald SPRT y Piso Cero-Perdida**: Evalua la continuacion del impulso, protege ganancias con el `Early Break-Even Ratchet`, ejecuta cosechas pasivas `DIAMOND Phase 2` y evacua posiciones estancadas a los `18.0s` (`MAKER_SCRATCH_18S`).

---

## 2. Estructura del Repositorio (45/45 Archivos Certificados en Gate 0)

### A. Orquestadores en Raiz (10 Modulos)
* `main.py`: Cerrojo de instancia unica (`.tribrain.lock`), reconciliador de arranque, auto-recarga atomica (`os.execv`) y bucle central.
* `config_parametros.py`: Catalogo maestro de 100 constantes (`AST_100_CONSTANTES_OK`) y recarga en caliente OOS (`< 0.5 ms`).
* `core_estado_ram.py`: Estado O(1) en RAM, cerrojos pre-fill y cola forense de `+15s`.
* `radar_volatilidad.py`: Orquestador WebSocket L2 a `25.0 Hz`, silenciador de slot activo y enrutador de senales.
* `ejecutor_sniper.py`: Orquestador de ordenes `PostOnly`, monitoreo de cola L1 y captura post-cancelacion.
* `gestor_posiciones.py`: Orquestador de posiciones abiertas (Wald SPRT, Break-Even Ratchet, Diamond Phase 2 y Scratch 18s).
* `escudo_tricortex.py`: Orquestador asincrono Groq LPU, matriz direccional y dimensionamiento Kelly.
* `stats_tracker.py`: Caja Negra (`tribrain_stats_v1.jsonl`) con paridad 1:1 Bybit UTA y LVR continuo.
* `telemetria_telegram.py`: Notificaciones transaccionales 1:1 en Telegram sin duplicados.
* `evaluador_cuantico_oos.py`: Calibrador Bayesiano Walk-Forward (72h) y Gemelo Digital (3,456 combinaciones).

### B. Paquete `ofensiva/` (11 Micro-Modulos + `__init__.py`)
* `micro_motor_maker.py`, `micro_motor_wald_exit.py`, `micro_sizing_kelly.py`, `micro_cotizador_stoikov.py`, `micro_cresta_convexo_sprt.py`, `micro_conviccion_kelly.py`, `micro_enganche_fase.py`, `micro_impulso_runner.py`, `micro_escudo_diamante_fase2.py`, `micro_retenedor_fill_parcial.py`, `micro_desarme_unwind_pasivo.py`.

### C. Paquete `defensiva/` (7 Micro-Modulos + `__init__.py`)
* `micro_escudos_fisicos.py`, `micro_veto_macro_btc.py`, `micro_cortafuegos_contagio.py`, `micro_evacuador_scratch.py`, `micro_escape_reconciliador.py`, `micro_candado_climax_hurst.py`, `micro_decaimiento_chronos_sl.py`.

### D. Paquete `apoyo/` (7 Micro-Modulos + `__init__.py`)
* `micro_cinematica_l2.py`, `micro_paridad_lvr_uta.py`, `micro_hud_ansi_telegram.py`, `micro_gemelo_digital_oos.py`, `micro_higiene_disco.py`, `micro_inspector_forense.py`, `micro_sensibilidad_autonoma.py`.

### E. Infraestructura, Pruebas y Configuracion (7 Archivos)
* `tools/validate_pool.py`, `test_tribrain_v1_suite.py`, `instalar_infraestructura.sh`, `calibracion_oos.json`, `requirements.txt`, `.gitignore`, `README.md`.

---

## 3. Comandos de Operacion y Control de Servicio (`verbot`)

Presionar `Ctrl+C` dentro de cualquier vista de `verbot` cierra unicamente la pantalla actual sin detener jamas el demonio HFT.

### Gestion del Servicio (`systemd`)
* `verbot status`          : Estado del servicio, PID activo, Uptime, CPU/RAM, prioridad `Nice=-10` y ultimas trazas.
* `verbot start`           : Inicia el motor verificando el cerrojo fisico `.tribrain.lock`.
* `verbot stop`            : Detiene limpiamente (`SIGTERM`) el servicio y libera `.tribrain.lock`.
* `verbot restart`         : Recarga atomica en caliente (`os.execv < 400 ms`) cuando `Slots == 0/1`.
* `verbot restart --hard`  : Reinicio completo del servicio mediante `systemd`.
* `verbot enable` / `disable`: Habilita o deshabilita el arranque automatico al iniciar el servidor Linux.

### Telemetria, Auditoria Forense e Inspeccion
* `verbot`                 : Consola en vivo a `25.0 Hz` con marcador `[BLACK BOX]` y flujo ANSI coloreado.
* `verbot -s`              : Resumen instantaneo (snapshot) de la Caja Negra y estado actual.
* `verbot -a`              : Inspector Forense Anatomico (PnL por par, Fill Rate, escudos `+15s` y markouts `+60s`).
* `verbot -i`              : Auditoria de baja latencia del kernel Linux (`bbr`, `fq`, `swappiness=1`, reloj NTP).
* `verbot -q`              : Reporte del calibrador cuantico OOS y parametros activos en `calibracion_oos.json`.
* `verbot -l`              : Simulacion del Gemelo Digital sobre 3,456 combinaciones.
* `verbot -h [filtro]`     : Historial filtrado (`trades`, `radar`, `ia`, `error`).
* `man verbot`             : Abre el manual tecnico oficial de UNIX (`VERBOT(1)`).

---

## 4. Verificacion Rapida (Gate 0 + Suite 18/18)

    python tools/validate_pool.py --sanitize
    python tools/validate_pool.py
    python test_tribrain_v1_suite.py
