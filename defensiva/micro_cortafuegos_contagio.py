# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #3: Filtro Estructural Anti-LUNA, Matriz Direccional
Cuantitativa con Entropia Markoviana LOB y Gobernador Elastico de Cuarentenas
Post-Perdida para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
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
    irrev_lob: float = 0.0,
) -> str:
    vetado, _ = evaluar_filtro_anti_luna(symbol, dp_pct, ofi)
    if vetado:
        return ram.MODO_DIRECCIONAL_VETO

    irrev = float(irrev_lob or 0.0)
    if symbol and irrev == 0.0 and not cfg.es_modo_test():
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if m_live is not None:
            irrev = float(getattr(m_live, "irrev_lob", 0.0) or 0.0)

    cascada_bajista_entropica = (
        (irrev >= 0.82 or z_score <= -3.50) and dp_pct <= -0.014 and ofi <= -0.50 and hurst >= 0.53
    )
    cascada_alcista_entropica = (
        (irrev >= 0.82 or z_score >= 3.50) and dp_pct >= 0.014 and ofi >= 0.50 and hurst >= 0.53
    )

    if (dp_pct <= -0.018 and ofi <= -0.55 and hurst >= 0.56) or cascada_bajista_entropica:
        modo = ram.MODO_DIRECCIONAL_SOLO_SHORT
    elif (dp_pct >= 0.018 and ofi >= 0.55 and hurst >= 0.56) or cascada_alcista_entropica:
        modo = ram.MODO_DIRECCIONAL_SOLO_LONG
    else:
        modo = ram.MODO_DIRECCIONAL_DUAL
    ram.ESTADO_GLOBAL.aplicar_matriz_direccional_lpu(symbol=symbol, modo=modo, motivo="QUANT_MATRIX")
    return modo


def calcular_segundos_cuarentena_post_perdida(
    motivo: str,
    pnl_usdt: float = 0.0,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
) -> float:
    """
    Calcula la cuarentena post-perdida proporcional a la severidad y friccion de salida:
    - SL_INTERNO_CHRONOS / SL_EXCHANGE: 240.0s base (hasta 300.0s en vivo si colapsa L2).
    - ESCAPE_TEMPORAL (90s Taker): 110.0s base + 5.0s por repeg fallido (hasta 140.0s).
    - TRINQUETE_BE_MAKER en perdida Taker: 90.0s base.
    - Otros cierres: 75.0s base.
    """
    mot_up = str(motivo).upper()
    if "SL" in mot_up:
        base_sl = float(cfg.obtener_aux("COOLDOWN_POST_SL_SEG", 240.0))
        if cfg.es_modo_test():
            return base_sl
        v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
        extra_sl = 30.0 if (float(pnl_usdt or 0.0) <= -0.070 or v_l2 < 0.45) else 0.0
        return round(min(300.0, base_sl + extra_sl), 1)

    base_sc = float(cfg.obtener_aux("COOLDOWN_MAKER_SCRATCH_18S", 75.0))
    if cfg.es_modo_test():
        return base_sc

    n_rep = max(0, int(repeg_salida_count or 0))
    if "ESCAPE_TEMPORAL" in mot_up:
        return round(min(140.0, max(110.0, base_sc + 35.0) + (5.0 * min(6, n_rep))), 1)
    if "TRINQUETE_BE" in mot_up:
        return round(min(120.0, max(90.0, base_sc + 15.0) + (4.0 * min(5, n_rep))), 1)
    return round(min(110.0, base_sc + (3.0 * min(6, n_rep))), 1)
