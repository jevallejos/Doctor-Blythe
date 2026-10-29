# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #9: Motor [DIAMOND] Phase 2 Maker Shield PostOnly con
Proyeccion Elastica en Cresta para Impulsos Fuertes (Lambda >= 2.80), Expansion
en Vacio de Liquidez L2 (orderbook.50), Front-Running Quirurgico de Muros
Institucionales y Cadencia Adaptativa de Re-Peg para HFT Doctor Blythe Terpsichora V7.0.
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_cotizador_stoikov as mcs


def evaluar_activacion_escudo_diamante_fase2(
    direccion: str,
    precio_entrada: float,
    precio_actual: float,
    best_bid: float,
    best_ask: float,
    edad_seg: float,
    pnl_pct: float,
    lambda_wald: float,
    tick_size: float,
    fase2_ya_ejecutada: bool = False,
    muro_opuesto_px: float = 0.0,
    vacio_l2_ratio: float = 1.0,
) -> Tuple[bool, float]:
    """
    Gobierna el [DIAMOND] Phase 2 Maker Shield PostOnly:
    1. Acopla el umbral de activacion al peso autonomo w3_tp_maker_pct y proyecta
       elasticamente la cresta (+0.180% a +0.265%) en funcion de vacio_l2_ratio
       y lambda_wald para no truncar runners con libro despejado.
    2. Si el escaner L2 detecta un Muro Institucional (muro_opuesto_px > 0) dentro de
       la zona de ganancia, coloca la orden PostOnly exactamente 1 tick delante del muro.
    """
    if fase2_ya_ejecutada or edad_seg < 18.0 or precio_entrada <= 0.0:
        return False, 0.0

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    tp_ctrl = float(ctrl.get("w3_tp_maker_pct", cfg.COSECHA_TRIZ_ACTIVACION_PCT))
    piso_pnl_f2 = max(0.00125, min(0.00145, tp_ctrl - 0.00005))
    if pnl_pct < piso_pnl_f2 or lambda_wald < 0.60:
        return False, 0.0

    t_sz = max(1e-8, float(tick_size))
    es_long = str(direccion).upper() in ("BUY", "LONG")
    v_l2 = max(0.20, min(3.00, float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)))
    vacio_runner = (v_l2 >= 1.45) and (lambda_wald >= 1.40) and (edad_seg < 38.0)
    impulso_fuerte_en_curso = ((lambda_wald >= 2.80) or vacio_runner) and (pnl_pct < 0.00215) and (edad_seg < 38.0)

    bono_vacio = 0.00035 * max(0.0, v_l2 - 1.20)
    bono_wald = 0.00010 * max(0.0, float(lambda_wald) - 2.00)
    target_cresta_pct = max(0.00180, min(0.00265, 0.00180 + bono_vacio + bono_wald))

    if es_long:
        if impulso_fuerte_en_curso:
            px_cresta = precio_entrada * (1.0 + target_cresta_pct)
            px_obj = mcs.cuantizar_tick(max(best_ask + t_sz, precio_actual + (2.0 * t_sz), px_cresta), t_sz, modo="ceil")
        else:
            px_obj = mcs.cuantizar_tick(max(best_ask, precio_actual + t_sz), t_sz, modo="ceil")

        if muro_opuesto_px > 0.0:
            px_front_wall = mcs.cuantizar_tick(muro_opuesto_px - t_sz, t_sz, modo="floor")
            piso_min_wall = precio_entrada * (1.0 + max(0.00115, float(cfg.TRINQUETE_BE_OFFSET_PCT) + 0.0004))
            if px_front_wall >= max(best_ask, piso_min_wall):
                px_obj = min(px_obj, px_front_wall) if px_obj > px_front_wall else px_obj

        if px_obj <= precio_entrada:
            return False, 0.0
        return True, px_obj
    else:
        if impulso_fuerte_en_curso:
            px_cresta = precio_entrada * (1.0 - target_cresta_pct)
            px_obj = mcs.cuantizar_tick(min(best_bid - t_sz, precio_actual - (2.0 * t_sz), px_cresta), t_sz, modo="floor")
        else:
            px_obj = mcs.cuantizar_tick(min(best_bid, precio_actual - t_sz), t_sz, modo="floor")

        if muro_opuesto_px > 0.0:
            px_front_wall = mcs.cuantizar_tick(muro_opuesto_px + t_sz, t_sz, modo="ceil")
            techo_max_wall = precio_entrada * (1.0 - max(0.00115, float(cfg.TRINQUETE_BE_OFFSET_PCT) + 0.0004))
            if px_front_wall <= min(best_bid, techo_max_wall):
                px_obj = max(px_obj, px_front_wall) if px_obj < px_front_wall else px_obj

        if px_obj >= precio_entrada:
            return False, 0.0
        return True, px_obj


def calcular_intervalo_repeg_salida_maker(
    motivo: str,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
) -> float:
    """
    Cadencia elastica de re-cotizacion PostOnly de salida:
    - Acelera el re-peg (hasta 0.55s) cuando el soporte L2 se evapora (vacio_l2_ratio < 0.65)
      o cuando ya se acumulan re-pegs sin llenar, logrando salir como Maker antes del SL Taker.
    - En vacio favorable (vacio_l2_ratio >= 1.35) y 0 repegs, conserva prioridad de cola (1.12x).
    """
    m_up = str(motivo).upper()
    if "UNWIND" in m_up or "HARVEST" in m_up or "TRAILING" in m_up or "WALD" in m_up:
        base_seg = float(cfg.COSECHA_REPEG_INTERVALO_SEG)
    else:
        base_seg = 1.60

    n_rep = max(0, int(repeg_salida_count or 0))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    factor_repeg = max(0.64, 1.0 - (0.12 * min(3, n_rep)))
    factor_vacio = 0.78 if v_l2 < 0.65 else (1.12 if (v_l2 >= 1.35 and n_rep == 0) else 1.00)
    return round(max(0.55, min(2.00, base_seg * factor_repeg * factor_vacio)), 3)


def verificar_disparo_fisico_trinquete_be(
    side: str,
    trinquete_be_armado: bool,
    sl_actual: float,
    entry_price: float,
    current_price: float,
    be_offset_pct: float = 0.00065,
) -> tuple[bool, float]:
    if not trinquete_be_armado or current_price <= 0.0 or entry_price <= 0.0:
        return False, float(sl_actual)
    offset_seguro = max(
        float(be_offset_pct),
        float(cfg.TRINQUETE_BE_OFFSET_PCT),
        (cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT) * 1.15,
    )
    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        piso_be = round(entry_price * (1.0 + offset_seguro), 8)
        sl_efectivo = max(float(sl_actual), piso_be) if sl_actual > 0 else piso_be
        return bool(current_price <= sl_efectivo), sl_efectivo
    else:
        techo_be = round(entry_price * (1.0 - offset_seguro), 8)
        sl_efectivo = min(float(sl_actual), techo_be) if sl_actual > 0 else techo_be
        return bool(current_price >= sl_efectivo), sl_efectivo
