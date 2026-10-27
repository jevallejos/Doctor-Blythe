# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Dimensionamiento Kelly y Anti-Trampa de Margen UTA.
Resuelve el bug de margen libre cacheado post-cierre ($9.25 - $5.75 = $3.50 USDT -> $6.53 nocional)
cuando Slots == 0/1, restituyendo la potencia completa (~$16.50-$17.25 USDT) en tiros ganadores.
"""
import inspect
from typing import Any, Tuple
import config_parametros as cfg
import core_estado_ram as ram


def sanear_balance_libre_slot_vacio(balance_libre_crudo: float) -> float:
    """
    Cuando no hay posiciones abiertas (Slots 0/1) ni ordenes en vuelo, verifica si el
    balance_libre_crudo quedo artificialmente reducido en cache por el margen de la
    operacion anterior (ej. $3.50 USDT en vez de $9.25 USDT). De ser asi, restituye
    el balance real sincronizado de la cuenta UTA.
    """
    libre = float(balance_libre_crudo or 0.0)
    est = getattr(ram, "ESTADO_GLOBAL", None)
    if est is None:
        return libre

    pos_abiertas = getattr(est, "posiciones_abiertas", {}) or {}
    ord_vuelo = getattr(est, "ordenes_en_vuelo", {}) or {}
    if len(pos_abiertas) > 0 or len(ord_vuelo) > 0:
        return libre

    # Buscar el balance total real sincronizado en ESTADO_GLOBAL
    candidatos_total = [
        float(getattr(est, attr, 0.0) or 0.0)
        for attr in ("balance_total_uta", "balance_uta_usdt", "equity_uta_usdt", "balance_real_usdt")
    ]
    total_real = max(candidatos_total) if candidatos_total else 0.0

    if total_real > 0.0 and libre > 0.0 and libre < (total_real * 0.85):
        return round(max(libre, total_real * 0.98), 4)

    return libre


def calcular_dimension_kelly_uta(
    tri_mod: Any,
    *args: Any,
    **kwargs: Any,
) -> Tuple[float, float, float]:
    """
    Envoltorio transparente para tri.calcular_dimension_kelly que inspecciona los
    argumentos sin importar su orden y sanea el parametro de capital/balance cuando Slots == 0/1.
    """
    fn = tri_mod.calcular_dimension_kelly
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        for nombre_param, valor in list(bound.arguments.items()):
            if any(k in nombre_param.lower() for k in ("balance", "capital", "usdt", "libre", "equity")):
                if isinstance(valor, (int, float)):
                    bound.arguments[nombre_param] = sanear_balance_libre_slot_vacio(float(valor))
                    break
        return fn(*bound.args, **bound.kwargs)
    except Exception:
        return fn(*args, **kwargs)
