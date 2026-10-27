"""
Level 0 DAG: Global Configuration & Immutable Parameter Contract for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
Maintains the strict 100-uppercase-constant invariant (AST_100_CONSTANTES_OK),
sub-millisecond OOS JSON hot-reload, and Terpsichora V1.0 offensive dynamics.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Dict, Tuple

# ==============================================================================
# GROUP 1: SYSTEM IDENTITY, RUNTIME MODE & EXCHANGE UNIVERSE (#001 - #015)
# ==============================================================================
VERSION_SISTEMA: str = "1.0.0"
NOMBRE_ESTRATEGIA: str = "HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0"
CODIGO_ESTRATEGIA: str = "DOCTOR-BLYTHE-TERPSICHORA-V1.0"
MODO_PAPER_TRADING: bool = False
MODO_EJECUCION_LIVE: bool = True
EXCHANGE_ID: str = "bybit"
TIPO_MERCADO: str = "swap"
MONEDA_BASE: str = "USDT"
PARES_CAMPEONES: Tuple[str, ...] = (
    "ZEREBRO/USDT:USDT",
    "WAL/USDT:USDT",
    "XRP/USDT:USDT",
    "AVAX/USDT:USDT",
    "TAO/USDT:USDT",
    "ARB/USDT:USDT",
)
PAR_LIDER_MACRO: str = "BTC/USDT:USDT"
UNIVERSO_PARES_TOTAL: Tuple[str, ...] = (
    "BTC/USDT:USDT",
    "ZEREBRO/USDT:USDT",
    "WAL/USDT:USDT",
    "XRP/USDT:USDT",
    "AVAX/USDT:USDT",
    "TAO/USDT:USDT",
    "ARB/USDT:USDT",
)
CLASE_HIGH_BETA: str = "CLASE_HIGH_BETA"
CLASE_TIER1_LIQUIDO: str = "CLASE_TIER1_LIQUIDO"
PARES_HIGH_BETA: Tuple[str, ...] = (
    "ZEREBRO/USDT:USDT",
    "WAL/USDT:USDT",
)
PARES_TIER1_LIQUIDOS: Tuple[str, ...] = (
    "XRP/USDT:USDT",
    "AVAX/USDT:USDT",
    "TAO/USDT:USDT",
    "ARB/USDT:USDT",
)

# ==============================================================================
# GROUP 2: CAPITAL, LEVERAGE, SLOTS & ASYMMETRIC KELLY SIZING (#016 - #030)
# ==============================================================================
CAPITAL_BASE_HISTORICO_USDT: float = 9.2119
APALANCAMIENTO_OPERATIVO: int = 3
APALANCAMIENTO_MAXIMO_PERMITIDO: int = 3
ORDEN_MINIMA_BYBIT_USDT: float = 5.50
MARGEN_SEGURIDAD_LIQUIDACION: float = 0.15
SLOTS_CONCURRENTES_MAX: int = 1
MAX_POSICIONES_POR_DIRECCION: int = 1
FRACCION_MINIMA_FILL_LOTE: float = 0.15
KELLY_FRACCION_BASE: float = 0.55
KELLY_FRACCION_MIN: float = 0.35
KELLY_FRACCION_MAX: float = 0.62
KELLY_SHORT_SNIPER_FRACCION: float = 0.60
KELLY_LONG_TIER1_FRACCION: float = 0.48
MULTIPLICADOR_IA_DEFAULT: float = 1.00
MULTIPLICADOR_IA_MIN: float = 0.50

# ==============================================================================
# GROUP 3: SAMPLING CADENCE, WINDOWS & BIPOWER SEASONALITY (#031 - #042)
# ==============================================================================
MULTIPLICADOR_IA_MAX: float = 1.15
FRECUENCIA_RADAR_HZ: float = 25.0
INTERVALO_RADAR_SEG: float = 0.040
VENTANA_Z_TICKS: int = 225
VENTANA_Z_MIN_TICKS: int = 60
EMA_MACRO_TICKS: int = 3375
EMA_RAPIDA_TICKS: int = 225
HURST_VENTANA_TICKS: int = 28
LYAPUNOV_VENTANA_TICKS: int = 5
VOLATILIDAD_BV_PISO_MIN: float = 0.00055
PERCENTIL_DIA_MIN: float = 0.05
PERCENTIL_DIA_MAX: float = 0.99

# ==============================================================================
# GROUP 4: TERPSICHORA PHASE-LATCHED RADAR & EMA900 DISLOCATION (#043 - #058)
# ==============================================================================
PHASE_LATCH_VENTANA_SEG: float = 4.50
FACTOR_RECORRIDO_MIN_EMA900: float = 1.65
Z_SCORE_UMBRAL_HIGH_BETA: float = -2.50
Z_SCORE_UMBRAL_TIER1: float = -2.15
Z_SCORE_TECHO_EXTREMO: float = -8.50
Z_SCORE_SHORT_UMBRAL: float = 1.80
Z_SCORE_IGNICION_SHORT_VETO: float = 5.20
DP_MIN_EXCURSION_LONG_HB: float = -0.0025
DP_MIN_EXCURSION_LONG_T1: float = -0.0016
DP_MIN_EXCURSION_SHORT_HB: float = 0.0022
DP_MIN_EXCURSION_SHORT_T1: float = 0.0016
EMA900_DISTANCIA_MIN_LONG_HB: float = -0.0024
EMA900_DISTANCIA_MIN_LONG_T1: float = -0.0016
EMA900_SOBREEXTENSION_SHORT_HB: float = 0.0034
EMA900_SOBREEXTENSION_SHORT_T1: float = 0.0028
EMA900_MAX_SOBRECOMPRA_LONG: float = 0.0042

# ==============================================================================
# GROUP 5: MICROSTRUCTURAL SHIELDS - HURST, LYAPUNOV, HAWKES, OFI (#059 - #076)
# ==============================================================================
HURST_MAX_ENTRADA_LONG: float = 0.485
HURST_MAX_ENTRADA_LONG_T1: float = 0.482
HURST_MAX_ENTRADA_SHORT: float = 0.485
HURST_TECHO_DURO_ABSOLUTO: float = 0.490
LYAPUNOV_ACEL_UMBRAL_FRENADO: float = -0.00022
LYAPUNOV_BUFFER_CHOQUE_BASE_SEG: float = 2.40
LYAPUNOV_BUFFER_TECHO_SEG: float = 8.50
HAWKES_DECAY_BETA: float = 1.85
HAWKES_INTENSIDAD_MIN_LONG: float = 0.08
HAWKES_INTENSIDAD_MAX_SHORT: float = -0.08
HAWKES_MEMORIA_PULSO_SEG: float = 0.25
OFI_NIVELES_PROFUNDO: int = 5
OFI_PESOS_NIVELES: Tuple[float, ...] = (0.40, 0.25, 0.15, 0.12, 0.08)
OFI_MIN_ENTRADA: float = 0.13
OFI_MIN_ENTRADA_TIER1: float = 0.13
OFI_MAX_ENTRADA_SHORT: float = -0.28
OFI_TICKS_PERSISTENCIA_MIN: int = 2
VPIN_MAX_TOXICIDAD: float = 0.42

# ==============================================================================
# GROUP 6: MACRO BTC VETO, CONTAGION & SMART PASSIVE EXECUTION (#077 - #090)
# ==============================================================================
SPREAD_MAX_PERMITIDO_PCT: float = 0.0018
BTC_VETO_Z_UMBRAL_CAIDA: float = -1.50
BTC_VETO_Z_UMBRAL_SUBIDA: float = 1.45
BTC_VETO_OFI_UMBRAL: float = 0.32
BTC_VETO_COOLDOWN_SEG: float = 12.0
CONTAGIO_PARES_SIMULTANEOS: int = 3
CONTAGIO_VENTANA_SEG: float = 10.0
PAUSA_MACRO_CONTAGIO_SEG: float = 30.0
TTL_ORDEN_ENTRADA_SEG: float = 3.80
PERMITIR_REQUOTE_ENTRADA: bool = True
REPEG_PASIVO_ENTRADA_SEG: float = 0.65
REPEG_DRIFT_MAX_PCT: float = 0.0015
EARLY_QUEUE_ABORT_SEG: float = 0.80
LATENCIA_ACK_BYBIT_MS: int = 120

# ==============================================================================
# GROUP 7: TERPSICHORA ACTIVE HARVEST, WALD SPRT & LEDGERS (#091 - #100)
# ==============================================================================
OFFSET_PENNY_JUMP_TICKS: int = 1
COMISION_MAKER_PCT: float = 0.00020
COMISION_TAKER_PCT: float = 0.00055
COSECHA_TRIZ_ACTIVACION_PCT: float = 0.0022
COSECHA_TRIZ_FRACCION_LOTE: float = 1.00
COSECHA_ESTANCAMIENTO_MFE_PCT: float = 0.0011
COSECHA_REPEG_INTERVALO_SEG: float = 1.20
TRINQUETE_BE_OFFSET_PCT: float = 0.00065
SL_INTERNO_PCT: float = 0.0045
TIEMPO_MAX_HOLD_SEG: float = 90.0

# ==============================================================================
# LOWERCASE RUNTIME HELPERS, AUXILIARY PATHS & HOT-RELOAD ENGINE
# ==============================================================================
_ruta_base = pathlib.Path(__file__).resolve().parent

_mapa_clase_activo: Dict[str, str] = {
    "ZEREBRO/USDT:USDT": CLASE_HIGH_BETA,
    "WAL/USDT:USDT": CLASE_HIGH_BETA,
    "XRP/USDT:USDT": CLASE_TIER1_LIQUIDO,
    "AVAX/USDT:USDT": CLASE_TIER1_LIQUIDO,
    "TAO/USDT:USDT": CLASE_TIER1_LIQUIDO,
    "ARB/USDT:USDT": CLASE_TIER1_LIQUIDO,
}

_limites_shadow_gate: Dict[str, Tuple[float, float]] = {
    "KELLY_FRACCION_BASE": (0.25, 0.62),
    "Z_SCORE_UMBRAL_HIGH_BETA": (-3.20, -2.20),
    "Z_SCORE_UMBRAL_TIER1": (-2.90, -1.95),
    "OFI_MIN_ENTRADA": (0.10, 0.25),
    "MAKER_SCRATCH_TIEMPO_SEG": (18.0, 45.0),
    "COSECHA_TRIZ_ACTIVACION_PCT": (0.0016, 0.0045),
    "SL_INTERNO_PCT": (0.0030, 0.0055),
    "TIEMPO_MAX_HOLD_SEG": (60.0, 120.0),
}

_parametros_operativos_aux: Dict[str, Any] = {
    "MAKER_SCRATCH_TIEMPO_SEG": 18.0,
    "MAKER_SCRATCH_OFI_ADVERSO": -0.15,
    "EARLY_UNWIND_TIEMPO_SEG": 42.0,
    "EARLY_UNWIND_MAX_MFE_PCT": 0.0006,
    "PRE_ESCAPE_MAKER_SEG": 72.0,
    "RETENCION_CUSTODIA_MAKER_MAX_SEG": 84.0,
    "TTL_SALIDA_MAKER_SEG": 4.20,
    "TRINQUETE_BE_BYBIT_OFFSET_PCT": 0.00060,
    "SL_EMERGENCIA_BYBIT_PCT": 0.0068,
    "COOLDOWN_POST_CIERRE_GANADOR_SEG": 25.0,
    "COOLDOWN_MAKER_SCRATCH_18S": 75.0,
    "COOLDOWN_POST_SL_SEG": 240.0,
    "STEP_LOCK_SHORT_SEG": 1800.0,
    "GROQ_TIMEOUT_SEG": 2.50,
    "MODELOS_GROQ_CORTEX1": (
        "allam-2-7b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ),
    "MODELOS_GROQ_CORTEX2": (
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "allam-2-7b",
    ),
    "MODELOS_GROQ_FORENSE": (
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
    ),
    "ARCHIVO_LOCK": ".tribrain.lock",
    "ARCHIVO_LOG": "bot_hft.log",
    "ARCHIVO_LOG_HISTORICO": "bot_hft_h.log",
    "ARCHIVO_STATS_JSONL": "tribrain_stats_v1.jsonl",
    "ARCHIVO_BAUL_IA_JSONL": "baul_ia_forense.jsonl",
    "ARCHIVO_CALIBRACION_OOS": "calibracion_oos.json",
    "ARCHIVO_REPORTE_OOS_MD": "reporte_cuantico_oos.md",
    "ARCHIVO_REPORTE_LAB_JSON": "reporte_lab_ia.json",
}

_ultimo_mtime_oos: float = 0.0


def es_modo_test() -> bool:
    return os.environ.get("TRIBRAIN_TEST_MODE") == "1"


def obtener_ruta_base() -> pathlib.Path:
    return _ruta_base


def obtener_clase_activo(symbol: str) -> str:
    return _mapa_clase_activo.get(symbol, CLASE_TIER1_LIQUIDO)


def obtener_aux(clave: str, default: Any = None) -> Any:
    if clave in globals():
        return globals()[clave]
    return _parametros_operativos_aux.get(clave, default)


def obtener_ruta_archivo(clave_o_nombre: str) -> pathlib.Path:
    if es_modo_test():
        if clave_o_nombre in ("ARCHIVO_LOG", "bot_hft.log"):
            return _ruta_base / ".test_bot_hft.log"
        if clave_o_nombre in ("ARCHIVO_LOCK", ".tribrain.lock"):
            return _ruta_base / ".tribrain_test.lock"
    nombre = _parametros_operativos_aux.get(clave_o_nombre, clave_o_nombre)
    return _ruta_base / str(nombre)


def sanitizar_dict_calibracion_oos(datos: Dict[str, Any]) -> Dict[str, float]:
    limpio: Dict[str, float] = {}
    fuente = datos.get("parametros_calibrados", datos) if isinstance(datos, dict) else {}
    if not isinstance(fuente, dict):
        return limpio
    for k, (vmin, vmax) in _limites_shadow_gate.items():
        if k in fuente:
            try:
                val = float(fuente[k])
                limpio[k] = max(vmin, min(vmax, val))
            except (TypeError, ValueError):
                continue
    return limpio


def recargar_calibracion_oos_si_cambio(ruta_json: str | pathlib.Path | None = None) -> Tuple[bool, float, Dict[str, float]]:
    global _ultimo_mtime_oos
    global KELLY_FRACCION_BASE, Z_SCORE_UMBRAL_HIGH_BETA, Z_SCORE_UMBRAL_TIER1
    global OFI_MIN_ENTRADA, COSECHA_TRIZ_ACTIVACION_PCT, SL_INTERNO_PCT, TIEMPO_MAX_HOLD_SEG

    t0 = time.perf_counter()
    target = pathlib.Path(ruta_json) if ruta_json else obtener_ruta_archivo("ARCHIVO_CALIBRACION_OOS")
    if not target.exists():
        return False, (time.perf_counter() - t0) * 1000.0, {}

    try:
        st_mtime = target.stat().st_mtime
        if st_mtime <= _ultimo_mtime_oos and ruta_json is None:
            return False, (time.perf_counter() - t0) * 1000.0, {}

        raw_data = json.loads(target.read_text(encoding="utf-8"))
        aplicados = sanitizar_dict_calibracion_oos(raw_data)
        if not aplicados:
            return False, (time.perf_counter() - t0) * 1000.0, {}

        if "KELLY_FRACCION_BASE" in aplicados:
            KELLY_FRACCION_BASE = aplicados["KELLY_FRACCION_BASE"]
        if "Z_SCORE_UMBRAL_HIGH_BETA" in aplicados:
            Z_SCORE_UMBRAL_HIGH_BETA = aplicados["Z_SCORE_UMBRAL_HIGH_BETA"]
        if "Z_SCORE_UMBRAL_TIER1" in aplicados:
            Z_SCORE_UMBRAL_TIER1 = aplicados["Z_SCORE_UMBRAL_TIER1"]
        if "OFI_MIN_ENTRADA" in aplicados:
            OFI_MIN_ENTRADA = aplicados["OFI_MIN_ENTRADA"]
        if "MAKER_SCRATCH_TIEMPO_SEG" in aplicados:
            _parametros_operativos_aux["MAKER_SCRATCH_TIEMPO_SEG"] = aplicados["MAKER_SCRATCH_TIEMPO_SEG"]
        if "COSECHA_TRIZ_ACTIVACION_PCT" in aplicados:
            COSECHA_TRIZ_ACTIVACION_PCT = aplicados["COSECHA_TRIZ_ACTIVACION_PCT"]
        if "SL_INTERNO_PCT" in aplicados:
            SL_INTERNO_PCT = aplicados["SL_INTERNO_PCT"]
        if "TIEMPO_MAX_HOLD_SEG" in aplicados:
            TIEMPO_MAX_HOLD_SEG = aplicados["TIEMPO_MAX_HOLD_SEG"]

        _ultimo_mtime_oos = st_mtime
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return True, elapsed_ms, aplicados
    except Exception:
        return False, (time.perf_counter() - t0) * 1000.0, {}


def __getattr__(name: str) -> Any:
    if name in _parametros_operativos_aux:
        return _parametros_operativos_aux[name]
    if name == "MAPA_CLASE_ACTIVO":
        return _mapa_clase_activo
    if name == "RUTA_BASE":
        return _ruta_base
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
