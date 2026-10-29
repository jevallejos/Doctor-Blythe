# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #2: Estimador Continuo de Seleccion Adversa (LOB LVR)
con Componente de Desplazamiento Glosten-Milgrom, Penalizacion por Friccion
de Re-Peg / Vacio L2 y Formateador del Panel ASCII de Caja Negra para
HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import math
from typing import Any, Dict, List
import config_parametros as cfg


def calcular_lvr_instantaneo(
    precio_entrada: float,
    precio_salida: float,
    duracion_seg: float,
    volatilidad_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    es_maker: bool = True,
    es_entrada_maker: bool = True,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
) -> float:
    """
    Calcula el Loss-Versus-Rebalancing (LOB LVR) instantaneo combinando:
    1. Termino difusivo de Milionis-Moallemi-Roughgarden: 0.5 * sigma^2 * sqrt(tau).
    2. Impacto direccional Glosten-Milgrom: 0.08 * |P_out - P_in| / P_in.
    3. Friccion de cola de salida (repeg_salida_count) y compresion L2 (vacio_l2_ratio).
    """
    if precio_entrada <= 0.0 or precio_salida <= 0.0:
        return 0.0005
    sigma = max(float(volatilidad_bv or cfg.VOLATILIDAD_BV_PISO_MIN), 0.00035)
    tau = max(1.0, min(float(duracion_seg or 18.0), 120.0)) / 9.0
    lvr_difusivo = 0.5 * (sigma ** 2) * math.sqrt(tau) * 10000.0
    desplazamiento_rel = min(0.025, abs(precio_salida - precio_entrada) / precio_entrada)
    lvr_compuesto = lvr_difusivo + (0.08 * desplazamiento_rel)

    if not cfg.es_modo_test():
        n_rep = max(0, int(repeg_salida_count or 0))
        v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
        friccion_cola = (0.00010 * min(8, n_rep)) + (0.00020 * max(0.0, 0.70 - v_l2))
        lvr_compuesto += friccion_cola

    if es_maker and es_entrada_maker:
        factor_ejecucion = 0.85
    elif es_maker or es_entrada_maker:
        factor_ejecucion = 1.35
    else:
        factor_ejecucion = 1.35 if cfg.es_modo_test() else 1.48

    return round(max(0.0001, min(0.0250, lvr_compuesto * factor_ejecucion)), 4)


def formatear_panel_ascii_resumen(r: Dict[str, Any]) -> List[str]:
    return [
        "+==================================================================+",
        (
            f"|  [BLACK BOX] DOCTOR-BLYTHE V7.0 | Trades: {r['trades']:<3d} "
            f"(W {r['wins']}/L {r['losses']}/S {r['scratches']}) | WR: {r['win_rate']:5.1f}%|"
        ),
        (
            f"|  Total PnL: {r['total_pnl_usdt']:+.4f} USDT   "
            f"best {r['best_usdt']:+.4f} / worst {r['worst_usdt']:+.4f}          |"
        ),
        (
            f"|  MAP: {r['map_usdt']:5.2f} USDT | "
            f"PnL/MAP: {r['pnl_over_map']:+.4f} | LVR: {r['lvr']:.4f}                |"
        ),
        (
            f"|  Balance: {r['balance_usdt']:.4f} USDT (base {r['base_usdt']:.2f})   "
            f"real: {r['real_usdt']:.4f} USDT            |"
        ),
        "+==================================================================+",
    ]
