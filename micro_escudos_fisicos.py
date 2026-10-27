# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Escudos Fisicos de Entrada (Terpsichora V1.0).
Aisla las 4 barreras cinematicas y de microestructura (Lyapunov, Hurst,
Absorcion OFI/Hawkes y Coherencia de Signo RF-06) fuera del motor WebSocket
de radar_volatilidad.py sin alterar ni un solo umbral de defensa.
"""
from typing import Tuple
import config_parametros as cfg


def evaluar_coherencia_signo_rf06(
    direccion: str,
    z_score: float,
    dp_pct: float,
) -> Tuple[bool, str]:
    """
    Ley RF-06: Proh?be disparar si el Z-Score y el desplazamiento porcentual (dp_pct)
    tienen signos contradictorios.
    """
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
    """
    Escudo Lyapunov Repulsor:
    - En LONG: bloquea si la caida sigue acelerando (a < umbral_freno_long).
    - En SHORT-SNIPER: exige desaceleracion/giro bajista confirmado (a <= umbral_agotamiento_short).
    """
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
    """
    Escudo Fractal de Hurst (HURST_FILTER & P-02_HURST_SHORT):
    Bloquea entradas contra-tendencia cuando la persistencia direccional H supera el tope.
    """
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
    """
    Escudo de Absorcion Microestructural (Arm-and-Fire [2/2t] + Intensidad de Hawkes):
    Exige absorcion real confirmada en la punta del libro antes de autorizar orden PostOnly.
    """
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
