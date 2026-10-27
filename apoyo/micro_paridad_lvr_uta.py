# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #2: Estimador Continuo de Seleccion Adversa (LOB LVR)
y Formateador del Panel ASCII de Caja Negra (1:1 UTA Parity).
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
) -> float:
    if precio_entrada <= 0.0 or precio_salida <= 0.0:
        return 0.0005
    sigma = max(float(volatilidad_bv or cfg.VOLATILIDAD_BV_PISO_MIN), 0.00035)
    tau = max(1.0, min(float(duracion_seg or 18.0), 120.0)) / 9.0
    lvr_teorico = 0.5 * (sigma ** 2) * math.sqrt(tau) * 100.0
    factor_ejecucion = 0.85 if es_maker else 1.35
    return round(max(0.0001, min(0.0250, lvr_teorico * factor_ejecucion)), 4)


def formatear_panel_ascii_resumen(r: Dict[str, Any]) -> List[str]:
    return [
        "+==================================================================+",
        (
            f"|  [BLACK BOX] DOCTOR-BLYTHE V1.0 | Trades: {r['trades']:<3d} "
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
