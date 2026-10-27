# HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0

Autonomous 25.0 Hz Limit Order Book (LOB) Microstructural Execution System for Bybit Unified Trading Account (UTA V5).

## Hexagonal Micro-Kernel Architecture (35 Canonical Files)

### Root Orchestrators (Pure I/O, State & Lifecycle Coordinators)
- **Level 0 (`config_parametros.py`)**: 100 immutable uppercase constants (`AST_100_CONSTANTES_OK`) & sub-ms OOS JSON hot-reload.
- **Level 1 (`core_estado_ram.py`)**: O(1) in-memory state machine, persistent line-buffered log I/O, and +15s counterfactual AI vault.
- **Level 2 (`telemetria_telegram.py`)**: 1:1 transactional Telegram notifications with 12s canonical deduplication.
- **Level 3 (`stats_tracker.py`)**: Transactional Black Box ledger (`tribrain_stats_v1.jsonl`) and 1:1 UTA parity orchestrator.
- **Level 4 (`escudo_tricortex.py`)**: Asynchronous Groq LPU ensemble orchestrator.
- **Level 5 (`radar_volatilidad.py`)**: 25.0 Hz L2 microstructural radar orchestrator and `SCAR-LOCK-00..18` ledger.
- **Level 6A (`ejecutor_sniper.py`)**: Passive `PostOnly` execution lifecycle and post-abort late-fill guard.
- **Level 6B (`gestor_posiciones.py`)**: Active position lifecycle governor and startup orphan reconciler.
- **Level 7 (`main.py`)**: Central 25.0 Hz WebSocket orchestrator, physical PID lock, and atomic `os.execv` auto-respawn across all 25 runtime modules.
- **Level 8 (`evaluador_cuantico_oos.py`)**: Walk-Forward OOS calibration orchestrator.

### 1. `ofensiva/` (7 Alpha Capture, Quoting, Sizing & Winner-Maximization Micro-Modules)
- `ofensiva/micro_motor_maker.py`: Moallemi L1 queue survival and directional Hurst permission on favorable OFI.
- `ofensiva/micro_motor_wald_exit.py`: Tick-quantized Zero-Loss floor (`SCAR-LOCK-14`), 22s early BE breathing room, and `MAKER_UNWIND` rally inhibitor.
- `ofensiva/micro_sizing_kelly.py`: Full-power UTA free-margin recovery when `Slots == 0/1`.
- `ofensiva/micro_cotizador_stoikov.py`: Stoikov micro-price pre-lead quoting (`Penny-Jump`), tick/lot quantization, and dynamic volatility TP.
- `ofensiva/micro_cresta_convexo_sprt.py`: Hyperbolic retention factor `kappa(MFE_t)` and Abraham Wald SPRT log-likelihood crest detector.
- `ofensiva/micro_conviccion_kelly.py`: Anti-fragile Kelly conviction bonuses and outlier convex expansion (`|Z| >= 8.0`).
- `ofensiva/micro_enganche_fase.py`: 4.50s Puppeteer Phase-Latched Envelope for `LONG` V-bottoms and `SHORT-SNIPER` top-rollovers.

### 2. `defensiva/` (4 Kinematic Shields, Macro BTC Veto, Contagion & Scratch Micro-Modules)
- `defensiva/micro_escudos_fisicos.py`: Lyapunov braking kinematics, directional Hurst caps, OFI/Hawkes absorption, and `RF-06` sign coherence.
- `defensiva/micro_veto_macro_btc.py`: Macro BTC circuit breaker (`Z <= -4.0`), 12s lead-lag cooldown, and synchronized reversal unlock.
- `defensiva/micro_cortafuegos_contagio.py`: Structural Anti-LUNA filter, quantitative directional matrix, and post-loss quarantine timer.
- `defensiva/micro_evacuador_scratch.py`: Pre-validated Bybit V5 `MarkPrice` SL geometry (`SEI-02`) and 18.0s passive `Maker-Scratch` (`RF-18`).

### 3. `apoyo/` (4 L2 Math Engines, UTA Parity/LVR, ANSI Live HUD & Digital Twin Micro-Modules)
- `apoyo/micro_cinematica_l2.py`: Jump-robust Bipower Variation `VentanaZ`, 5-level deep OFI, Hurst, Lyapunov, and 24h seasonality curve.
- `apoyo/micro_paridad_lvr_uta.py`: Continuous-time LOB LVR toxicity estimator and ASCII Black Box formatter.
- `apoyo/micro_hud_ansi_telegram.py`: Zero-disk-contamination ANSI live colorizer for `verbot`.
- `apoyo/micro_gemelo_digital_oos.py`: 72h Walk-Forward Bayesian metrics and 3,456-combination counterfactual Digital Twin (`--lab`).
