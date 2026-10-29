"""
Level 0 DAG: Global Configuration & Immutable Parameter Contract for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
Maintains the strict 100-uppercase-constant invariant (AST_100_CONSTANTES_OK),
sub-millisecond OOS JSON hot-reload, Non-Regressive Autonomous Controller Manifold
projection, and per-asset Bipower Variation elasticity reference profiles.
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
VERSION_SISTEMA: str = "7.0.0"
NOMBRE_ESTRATEGIA: str = "HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0"
CODIGO_ESTRATEGIA: str = "DOCTOR-BLYTHE-TERPSICHORA-V7.0"
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
OFI_MIN_ENTRADA: float = 0.05
OFI_MIN_ENTRADA_TIER1: float = 0.05
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
COSECHA_TRIZ_ACTIVACION_PCT: float = 0.0014
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

# Per-asset intrinsic Bipower Variation elasticity profile:
# (sigma_raw_floor, sigma_natural_ref, sigma_raw_ceiling)
# Used exclusively for intraday 24h percentile & elastic band scaling without
# relaxing SCAR-LOCK-00 (VOLATILIDAD_BV_PISO_MIN = 0.00055) in Z-Score denominator.
_perfil_elasticidad_bv_par: Dict[str, Tuple[float, float, float]] = {
    "ZEREBRO/USDT:USDT": (0.00042, 0.00082, 0.00145),
    "WAL/USDT:USDT": (0.00022, 0.00046, 0.00095),
    "ARB/USDT:USDT": (0.00014, 0.00032, 0.00075),
    "AVAX/USDT:USDT": (0.00014, 0.00030, 0.00072),
    "TAO/USDT:USDT": (0.00016, 0.00035, 0.00080),
    "XRP/USDT:USDT": (0.00012, 0.00028, 0.00068),
    "BTC/USDT:USDT": (0.00010, 0.00024, 0.00060),
}

_limites_shadow_gate: Dict[str, Tuple[float, float]] = {
    "KELLY_FRACCION_BASE": (0.25, 0.62),
    "Z_SCORE_UMBRAL_HIGH_BETA": (-3.20, -2.20),
    "Z_SCORE_UMBRAL_TIER1": (-2.90, -1.95),
    "OFI_MIN_ENTRADA": (0.05, 0.25),
    "MAKER_SCRATCH_TIEMPO_SEG": (18.0, 45.0),
    "COSECHA_TRIZ_ACTIVACION_PCT": (0.0012, 0.0045),
    "SL_INTERNO_PCT": (0.0030, 0.0055),
    "TIEMPO_MAX_HOLD_SEG": (60.0, 120.0),
}

_limites_controlador_autonomo: Dict[str, Tuple[float, float]] = {
    "w1_ofi_long": (0.05, 0.22),
    "w2_btc_beta": (0.24, 0.45),
    "w3_tp_maker_pct": (0.0012, 0.0035),
    "w4_unwind_seg": (26.0, 55.0),
    "w4_sl_decay_pct": (0.0028, 0.0042),
    "w5_kelly_short": (0.35, 0.62),
    "w5_kelly_long": (0.35, 0.58),
    "hurst_cap_short_mod": (0.450, 0.485),
    "mfe_stall_harvest_pct": (0.00085, 0.00150),
    "sesgo_escudo_long": (0.00, 0.05),
    "sesgo_escudo_short": (0.00, 0.05),
    "sens_ofi_abort_cola": (-0.48, -0.22),
    "sens_q_l1_hold_ratio": (0.18, 0.55),
    "sens_scratch_edad_rebote_seg": (20.0, 38.0),
    "sens_climax_hurst_override": (0.0, 1.0),
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


def obtener_perfil_elasticidad_bv(symbol: str) -> Tuple[float, float, float]:
    """
    Retorna (sigma_raw_floor, sigma_natural_ref, sigma_raw_ceiling) del par
    para el calculo del percentil intradia de 24h sin sesgo de truncamiento.
    """
    if symbol in _perfil_elasticidad_bv_par:
        return _perfil_elasticidad_bv_par[symbol]
    if obtener_clase_activo(symbol) == CLASE_HIGH_BETA:
        return (0.00025, 0.00060, 0.00120)
    return (0.00014, 0.00032, 0.00075)


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
        if clave_o_nombre in ("ARCHIVO_CALIBRACION_OOS", "calibracion_oos.json"):
            return _ruta_base / ".test_calibracion_oos.json"
        if clave_o_nombre in ("ARCHIVO_REPORTE_OOS_MD", "reporte_cuantico_oos.md"):
            return _ruta_base / ".test_reporte_cuantico_oos.md"
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


def sanitizar_controlador_autonomo(ctrl_raw: Dict[str, Any]) -> Dict[str, float]:
    """
    Proyecta ortogonalmente cualquier diccionario del controlador autonomo
    sobre la variedad compacta no-regresiva Omega_ctrl.
    """
    limpio: Dict[str, float] = {}
    if not isinstance(ctrl_raw, dict):
        return limpio
    for k, v in ctrl_raw.items():
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        if k in _limites_controlador_autonomo:
            vmin, vmax = _limites_controlador_autonomo[k]
            limpio[k] = round(max(vmin, min(vmax, val)), 5)
        elif k.startswith("alpha_disloc_"):
            limpio[k] = round(max(1.00, min(1.40, val)), 4)
        elif k.startswith("w_kelly_"):
            limpio[k] = round(max(0.72, min(1.12, val)), 4)
        elif k.startswith("edge_post_"):
            limpio[k] = round(max(0.50, min(2.50, val)), 4)
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
        try:
            import core_estado_ram as _ram_mod
            ctrl_json_raw = raw_data.get("controlador_autonomo")
            if isinstance(ctrl_json_raw, dict):
                ctrl_limpio = sanitizar_controlador_autonomo(ctrl_json_raw)
                ram_ctrl = _ram_mod.ESTADO_GLOBAL.controlador_autonomo
                for k_c, v_c in ctrl_limpio.items():
                    if k_c.startswith("alpha_disloc_") and k_c in ram_ctrl:
                        ram_ctrl[k_c] = round(max(float(ram_ctrl[k_c]), float(v_c)), 4)
                    elif k_c in ("sesgo_escudo_long", "sesgo_escudo_short") and k_c in ram_ctrl:
                        ram_ctrl[k_c] = round(max(float(ram_ctrl[k_c]), float(v_c)), 4)
                    else:
                        ram_ctrl[k_c] = float(v_c)
            _ram_mod.ESTADO_GLOBAL.controlador_autonomo["w1_ofi_long"] = float(OFI_MIN_ENTRADA)
            _ram_mod.ESTADO_GLOBAL.controlador_autonomo["w3_tp_maker_pct"] = float(COSECHA_TRIZ_ACTIVACION_PCT)
        except Exception:
            pass

        _ultimo_mtime_oos = st_mtime
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return True, elapsed_ms, aplicados
    except Exception:
        return False, (time.perf_counter() - t0) * 1000.0, {}


def __getattr__(name: str) -> Any:
    if name in _parametros_operativos_aux:
        return _parametros_operativos_aux[name]
    if name == "KELLY_TOPE_MAXIMO":
        return KELLY_FRACCION_MAX
    if name == "MAPA_CLASE_ACTIVO":
        return _mapa_clase_activo
    if name == "RUTA_BASE":
        return _ruta_base
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
