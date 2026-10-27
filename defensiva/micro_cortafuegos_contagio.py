# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #3: Filtro Estructural Anti-LUNA, Matriz Direccional
Cuantitativa y Gobernador de Cuarentenas Post-Perdida.
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


def evaluar_filtro_anti_luna(symbol: str, caida_pct: float, ofi: float) -> Tuple[bool, str]:
    if caida_pct <= -0.055 and ofi <= -0.80:
        ram.ESTADO_GLOBAL.aplicar_matriz_direccional_lpu(
            symbol=symbol,
            modo=ram.MODO_DIRECCIONAL_VETO,
            motivo=f"ANTI_LUNA_VETO(drop={caida_pct * 100:.1f}%,OFI={ofi:.2f})",
        )
        ram.log_operativo(
            f"[RAM SHIELD] Quantitative fallback veto on {symbol} "
            f"(drop {caida_pct * 100:.1f}%, OFI {ofi:+.2f})"
        )
        return True, ram.MODO_DIRECCIONAL_VETO
    return False, ram.MODO_DIRECCIONAL_DUAL


def evaluar_matriz_direccional_cuantitativa(
    symbol: str,
    z_score: float,
    dp_pct: float,
    ofi: float,
    hurst: float = 0.42,
) -> str:
    vetado, _ = evaluar_filtro_anti_luna(symbol, dp_pct, ofi)
    if vetado:
        return ram.MODO_DIRECCIONAL_VETO
    if dp_pct <= -0.018 and ofi <= -0.55 and hurst >= 0.56:
        modo = ram.MODO_DIRECCIONAL_SOLO_SHORT
    elif dp_pct >= 0.018 and ofi >= 0.55 and hurst >= 0.56:
        modo = ram.MODO_DIRECCIONAL_SOLO_LONG
    else:
        modo = ram.MODO_DIRECCIONAL_DUAL
    ram.ESTADO_GLOBAL.aplicar_matriz_direccional_lpu(symbol=symbol, modo=modo, motivo="QUANT_MATRIX")
    return modo


def calcular_segundos_cuarentena_post_perdida(motivo: str) -> float:
    if "SL" in str(motivo).upper():
        return float(cfg.obtener_aux("COOLDOWN_POST_SL_SEG", 240.0))
    return float(cfg.obtener_aux("COOLDOWN_MAKER_SCRATCH_18S", 75.0))
