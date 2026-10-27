# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #3: Dimensionamiento Kelly UTA y Anti-Trampa de Margen Libre.
Garantiza nocional completo (~$16.00-$17.25 USDT) cuando Slots == 0/1.
"""
from typing import Any, Tuple
import core_estado_ram as ram


def sanear_balance_libre_slot_vacio(balance_libre_crudo: float) -> float:
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
    capital_saneado = sanear_balance_libre_slot_vacio(capital_libre_usdt)
    return tri_mod.calcular_dimension_kelly(
        capital_libre_usdt=capital_saneado,
        z_score=z_score,
        ofi=ofi,
        hurst=hurst,
        side=side,
        symbol=symbol,
    )
