# HFT Doctor Blythe Engine ? Production Baseline Terpsichora V1.0

Autonomous 25.0 Hz Limit Order Book (LOB) Microstructural Execution System for Bybit Unified Trading Account (UTA V5).

## Core Architecture (17 Canonical Files)
- **Level 0 (`config_parametros.py`)**: 100 immutable uppercase constants (`AST_100_CONSTANTES_OK`) & sub-ms OOS JSON hot-reload.
- **Level 1 (`core_estado_ram.py`)**: O(1) in-memory state machine, persistent line-buffered log I/O, and +15s counterfactual AI vault.
- **Level 2 (`telemetria_telegram.py`)**: 1:1 transactional Telegram notifications with 12s canonical deduplication.
- **Level 3 (`stats_tracker.py`)**: Transactional Black Box ledger (`tribrain_stats_v1.jsonl`), 1:1 UTA parity, and continuous LOB-LVR tracker.
- **Level 4 (`escudo_tricortex.py`)**: Asynchronous Groq LPU ensemble, Anti-LUNA filter, and anti-fragile Kelly sizing with defensive shrinkage.
- **Level 5 (`radar_volatilidad.py`)**: 25.0 Hz L2 microstructural radar, Bipower Variation Z-Score, 1800ms Phase-Latched envelope, strict `sign(Z) == sign(dp)`, and `SCAR-LOCK-00..18`.
- **Level 6A (`ejecutor_sniper.py`)**: 100% passive `PostOnly` Penny-Jump execution, 1.0s passive re-peg, 0.8s Early Queue Abort, and MarkPrice SL geometry validation.
- **Level 6B (`gestor_posiciones.py`)**: Abraham Wald SPRT optimal stopping, tick-quantized net-of-fee Zero-Loss floor (`SCAR-LOCK-14`), +0.11% MFE early Break-Even shield, and 18.0s passive Maker-Scratch.
- **Level 7 (`main.py`)**: 25.0 Hz WebSocket orchestrator, physical PID lock, and zero-downtime `os.execv` auto-respawn.
- **Level 8 (`evaluador_cuantico_oos.py`)**: Walk-Forward OOS calibrator and 3,456-combination Counterfactual Digital Twin (`--lab`).
