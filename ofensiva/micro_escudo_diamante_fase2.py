# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #9: Motor [DIAMOND] Phase 2 Maker Shield PostOnly,
Control Estocastico Singular de Cosecha Parcial Condicionada theta*(t) (arXiv:2602.05025),
Piso de Trinquete Subsidiado para Contratos Runner, Expansion en Vacio L2 (orderbook.50),
Front-Running Quirurgico de Muros Institucionales y Cadencia Adaptativa de Re-Peg
para HFT Doctor Blythe Terpsichora V7.0.
"""
import math
from typing import Tuple

import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_cotizador_stoikov as mcs


def evaluar_cosecha_parcial_singular_hawkes(
    direccion: str,
    contratos_actuales: float,
    precio_entrada: float,
    precio_actual: float,
    best_bid: float,
    best_ask: float,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    lambda_wald: float,
    tick_size: float,
    step_size: float,
    cosecha_50_ya_ejecutada: bool = False,
    en_proceso_cierre: bool = False,
    vacio_l2_ratio: float = 1.0,
) -> Tuple[bool, float, float]:
    """
    Operador de Control Singular de Cosecha Parcial theta*(t) (arXiv:2602.05025):
    1. Verifica la restriccion de particion minima de Bybit UTA V5: tanto el lote
       cosechado como el lote runner remanente deben superar ORDEN_MINIMA_BYBIT_USDT (5.50 USDT).
    2. Calcula la frontera elastica de primer impulso b_part(V_L2, M_stall_auto):
       se adelanta hacia +0.078%..+0.088% cuando hay muro opuesto (V_L2 < 0.85) y
       se expande a +0.105%..+0.120% cuando el corredor L2 esta despejado.
    3. Inhibe la cosecha parcial si el activo va en aceleracion balistica en vacio
       (V_L2 >= 1.25, Lambda_Wald >= 1.80, OFI_dir >= +0.22) para no truncar runners puros.
    Retorna (activar_cosecha_parcial, fraccion_optima_theta, precio_post_only).
    """
    if (
        cfg.es_modo_test()
        or cosecha_50_ya_ejecutada
        or en_proceso_cierre
        or edad_seg < 4.5
        or contratos_actuales <= 0.0
        or precio_entrada <= 0.0
        or precio_actual <= 0.0
    ):
        return False, 0.0, 0.0

    min_notional = float(cfg.ORDEN_MINIMA_BYBIT_USDT)
    nocional_actual = abs(float(contratos_actuales) * float(precio_actual))
    if nocional_actual < (2.05 * min_notional):
        return False, 0.0, 0.0

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    tp_auto = float(ctrl.get("w3_tp_maker_pct", cfg.COSECHA_TRIZ_ACTIVACION_PCT))
    m_stall_auto = max(0.00100, float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT)))
    theta_auto = max(0.45, min(0.60, float(ctrl.get("w6_harvest_part_frac", 0.50) or 0.50)))

    v_l2 = max(0.20, min(3.00, float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)))
    es_long = str(direccion).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_5s) if es_long else -float(ofi_5s)
    lam_w = float(lambda_wald or 0.0)
    t_sz = max(1e-8, float(tick_size))
    s_sz = max(1e-8, float(step_size))

    spread_rel = ((best_ask - best_bid) / precio_actual) if (best_ask > best_bid and precio_actual > 0.0) else 0.0
    piso_fee_part = (2.0 * float(cfg.COMISION_MAKER_PCT)) + max(0.00038, spread_rel)
    mod_v2_part = max(0.72, min(1.05, 0.78 + 0.16 * math.tanh(v_l2 - 0.85)))
    b_part = max(piso_fee_part, m_stall_auto * mod_v2_part)

    if pnl_pct < b_part and mfe_pct < (b_part + 0.00012):
        return False, 0.0, 0.0
    if pnl_pct < (2.0 * float(cfg.COMISION_MAKER_PCT) + 0.00025):
        return False, 0.0, 0.0

    impulso_balistico_vacio = (v_l2 >= 1.25) and (lam_w >= 1.80) and (ofi_dir >= 0.22) and (pnl_pct < tp_auto)
    if impulso_balistico_vacio:
        return False, 0.0, 0.0

    frenado_primario = (
        (v_l2 < 0.95)
        or (ofi_dir <= 0.16)
        or (lam_w <= 1.35)
        or (pnl_pct >= tp_auto)
        or (mfe_pct >= (b_part + 0.00015) and pnl_pct <= (mfe_pct - 0.00012))
    )
    if not frenado_primario:
        return False, 0.0, 0.0

    theta_opt = max(
        0.45,
        min(
            0.60,
            theta_auto + 0.08 * math.tanh(0.85 - v_l2) - 0.04 * math.tanh(lam_w / 2.50),
        ),
    )
    lote_part = mcs.cuantizar_lote(contratos_actuales * theta_opt, s_sz)
    lote_rem = round(max(0.0, contratos_actuales - lote_part), 6)
    if (lote_part * precio_actual) < min_notional or (lote_rem * precio_actual) < (min_notional * 1.01):
        lote_part = mcs.cuantizar_lote(contratos_actuales * 0.50, s_sz)
        lote_rem = round(max(0.0, contratos_actuales - lote_part), 6)
        if (lote_part * precio_actual) < min_notional or (lote_rem * precio_actual) < (min_notional * 1.01):
            return False, 0.0, 0.0

    frac_efectiva = round(lote_part / contratos_actuales, 4)
    px_obj = mcs.cuantizar_tick(best_ask if es_long else best_bid, t_sz)
    if (es_long and px_obj <= precio_entrada) or ((not es_long) and px_obj >= precio_entrada):
        return False, 0.0, 0.0
    return True, frac_efectiva, px_obj


def calcular_piso_subsidiado_runner(
    precio_entrada: float,
    direccion: str,
    tick_size: float,
    pnl_realizado_parcial_usdt: float,
    nocional_restante_usdt: float,
) -> float:
    """
    Calcula el piso de proteccion subsidiado para los contratos runner restantes:
    Utiliza hasta el 55% de la ganancia neta ya cobrada en el Tramo 1 para darle
    mayor holgura anti-ruido al Tramo 2, garantizando siempre >= 2 * fee_maker
    sobre el tramo restante y ganancia neta global asegurada.
    """
    t_sz = max(1e-8, float(tick_size))
    offset_base = max(
        float(cfg.TRINQUETE_BE_OFFSET_PCT),
        (cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT) * 1.15,
    )
    piso_mkr_rt = (2.0 * float(cfg.COMISION_MAKER_PCT)) + 0.00005
    if pnl_realizado_parcial_usdt > 0.0 and nocional_restante_usdt > 0.0 and not cfg.es_modo_test():
        subsidio_rel = 0.55 * (float(pnl_realizado_parcial_usdt) / max(1.0, float(nocional_restante_usdt)))
        offset_eff = max(piso_mkr_rt, offset_base - subsidio_rel)
    else:
        offset_eff = offset_base

    if str(direccion).upper() in ("BUY", "LONG"):
        return mcs.cuantizar_tick(precio_entrada * (1.0 + offset_eff), t_sz, modo="ceil")
    return mcs.cuantizar_tick(precio_entrada * (1.0 - offset_eff), t_sz, modo="floor")


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
    pnl_realizado_parcial_usdt: float = 0.0,
    nocional_restante_usdt: float = 0.0,
) -> tuple[bool, float]:
    if not trinquete_be_armado or current_price <= 0.0 or entry_price <= 0.0:
        return False, float(sl_actual)
    offset_seguro = max(
        float(be_offset_pct),
        float(cfg.TRINQUETE_BE_OFFSET_PCT),
        (cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT) * 1.15,
    )
    if pnl_realizado_parcial_usdt > 0.0 and nocional_restante_usdt > 0.0 and not cfg.es_modo_test():
        subsidio_rel = 0.55 * (float(pnl_realizado_parcial_usdt) / max(1.0, float(nocional_restante_usdt)))
        offset_seguro = max((2.0 * float(cfg.COMISION_MAKER_PCT)) + 0.00005, offset_seguro - subsidio_rel)

    side_u = str(side).upper()
    if side_u in ("LONG", "BUY"):
        piso_be = round(entry_price * (1.0 + offset_seguro), 8)
        sl_efectivo = max(float(sl_actual), piso_be) if sl_actual > 0 else piso_be
        return bool(current_price <= sl_efectivo), sl_efectivo
    else:
        techo_be = round(entry_price * (1.0 - offset_seguro), 8)
        sl_efectivo = min(float(sl_actual), techo_be) if sl_actual > 0 else techo_be
        return bool(current_price >= sl_efectivo), sl_efectivo
