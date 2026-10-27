# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #1: Escudos Fisicos de Entrada (Terpsichora V1.0).
Aisla las barreras cinematicas y de microestructura (Lyapunov, Hurst,
Absorcion OFI/Hawkes, Coherencia de Signo RF-06 y Conviccion Contra-EMA900).
"""
from typing import Tuple


def evaluar_coherencia_signo_rf06(
    direccion: str,
    z_score: float,
    dp_pct: float,
) -> Tuple[bool, str]:
    if direccion == "LONG":
        if z_score >= 0.0 or dp_pct >= 0.0:
            return False, f"RF06_LONG_MISMATCH(Z={z_score:+.2f},dp={dp_pct:+.4f})"
    else:
        if z_score <= 0.0 or dp_pct <= 0.0:
            return False, f"RF06_SHORT_MISMATCH(Z={z_score:+.2f},dp={dp_pct:+.4f})"
    return True, "OK"


def evaluar_freno_lyapunov(
    direccion: str,
    aceleracion_lyapunov: float,
    umbral_freno_long: float = -0.00022,
    umbral_agotamiento_short: float = -0.00010,
) -> Tuple[bool, str]:
    if direccion == "LONG":
        if aceleracion_lyapunov < umbral_freno_long:
            return False, f"LYAPUNOV_REPULSOR(a={aceleracion_lyapunov:+.5f}<{umbral_freno_long:+.5f})"
    else:
        if aceleracion_lyapunov > umbral_agotamiento_short:
            return False, f"LYAPUNOV_SHORT_NO_BRAKE(a={aceleracion_lyapunov:+.5f}>{umbral_agotamiento_short:+.5f})"
    return True, "OK"


def evaluar_filtro_hurst_direccional(
    direccion: str,
    hurst_actual: float,
    hurst_max_long: float = 0.485,
    hurst_max_short: float = 0.485,
) -> Tuple[bool, str]:
    tope = hurst_max_long if direccion == "LONG" else hurst_max_short
    if hurst_actual > tope:
        etiqueta = "HURST_FILTER" if direccion == "LONG" else "P-02_HURST_SHORT"
        return False, f"{etiqueta}(H={hurst_actual:.3f}>{tope:.3f})"
    return True, "OK"


def evaluar_absorcion_ofi_hawkes(
    direccion: str,
    ofi_actual: float,
    ticks_absorcion: int,
    hawkes_actual: float,
    ofi_min_req: float = 0.13,
    ticks_min_req: int = 2,
    hawkes_min_req: float = 0.10,
) -> Tuple[bool, str]:
    if direccion == "LONG":
        if ofi_actual < ofi_min_req or ticks_absorcion < ticks_min_req:
            return (
                False,
                f"WAIT_BID_ABSORPTION(OFI={ofi_actual:+.2f}[{ticks_absorcion}/{ticks_min_req}t]<{ofi_min_req:+.2f})",
            )
        if hawkes_actual < hawkes_min_req:
            return False, f"HAWKES_WEAK_LONG(I={hawkes_actual:+.2f}<{hawkes_min_req:+.2f})"
    else:
        ofi_short_req = -abs(ofi_min_req)
        if ofi_actual > ofi_short_req or ticks_absorcion < ticks_min_req:
            return (
                False,
                f"WAIT_ASK_ABSORPTION(OFI={ofi_actual:+.2f}[{ticks_absorcion}/{ticks_min_req}t]>{ofi_short_req:+.2f})",
            )
    return True, "OK"


def evaluar_conviccion_contratendencia_ema900(
    direccion: str,
    ema900_dist_pct: float,
    ofi_actual: float,
    hurst_actual: float,
    z_score: float = 0.0,
) -> Tuple[bool, str]:
    """
    Escudo Contra-Tendencia Macro Extrema (Remediacion Trade #8 y Trade #2):
    Cuando |EMA900| >= 0.50% en contra de la direccion y no es un climax extremo (|Z| < 6.0),
    exige agotamiento fractal firme (H <= 0.435) y absorcion OFI profunda (|OFI| >= 0.42).
    """
    if abs(z_score) >= 6.0:
        return True, "OK"

    if direccion == "SHORT" and ema900_dist_pct >= 0.0050:
        if hurst_actual > 0.435 or ofi_actual > -0.42:
            return (
                False,
                f"WEAK_COUNTER_TREND_SHORT(EMA900={ema900_dist_pct * 100:+.2f}%,OFI={ofi_actual:+.2f},H={hurst_actual:.2f})",
            )
    elif direccion == "LONG" and ema900_dist_pct <= -0.0050:
        if hurst_actual > 0.435 or ofi_actual < 0.42:
            return (
                False,
                f"WEAK_COUNTER_TREND_LONG(EMA900={ema900_dist_pct * 100:+.2f}%,OFI={ofi_actual:+.2f},H={hurst_actual:.2f})",
            )
    return True, "OK"
