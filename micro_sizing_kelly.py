# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Dimensionamiento Kelly y Anti-Trampa de Margen UTA.
Resuelve el sub-dimensionamiento transitorio post-cierre/cancelacion ($6.28/$6.53 vs $17.24 USDT)
usando los atributos exactos de EstadoGlobalRAM (posiciones_activas, capital_total_uta, capital_libre_uta).
"""
from typing import Any, Tuple
import config_parametros as cfg
import core_estado_ram as ram


def sanear_balance_libre_slot_vacio(balance_libre_crudo: float) -> float:
    """
    Cuando no hay posiciones activas abiertas (Slots 0/1), verifica si capital_libre_uta
    quedo transitoriamente reducido en cache (< 85% de capital_total_uta) por una orden
    PostOnly reci?n cancelada o cerrada hace milisegundos, y restituye el 98% de capital_total_uta.
    """
    libre = float(balance_libre_crudo or 0.0)
    est = getattr(ram, "ESTADO_GLOBAL", None)
    if est is None:
        return libre

    pos_dict = getattr(est, "posiciones_activas", {}) or {}
    activas = [p for p in pos_dict.values() if not getattr(p, "cerrada", False)]
    if len(activas) > 0:
        return libre

    total_real = float(getattr(est, "capital_total_uta", 0.0) or 0.0)
    if total_real > 0.0 and libre > 0.0 and libre < (total_real * 0.85):
        return round(max(libre, total_real * 0.98), 4)

    return libre


def calcular_dimension_kelly_uta(
    tri_mod: Any,
    capital_libre_usdt: float,
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> Tuple[float, float, float]:
    """
    Envoltorio conectado a ejecutor_sniper.py que garantiza nocional completo (~$16.50-$17.25 USDT)
    en cada disparo cuando el slot esta libre (0/1).
    """
    capital_saneado = sanear_balance_libre_slot_vacio(capital_libre_usdt)
    return tri_mod.calcular_dimension_kelly(
        capital_libre_usdt=capital_saneado,
        z_score=z_score,
        ofi=ofi,
        hurst=hurst,
        side=side,
        symbol=symbol,
    )
