# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #7: Compresion Temporal Estocastica C1-Monotona del
Stop-Loss Interno (CHRONOS Time-Decay SL) Acoplada a Wald SPRT y Vacio Profundo L2
para Posiciones Estancadas (HFT Doctor Blythe Terpsichora V7.0).
"""
import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_cotizador_stoikov as mcs


def calcular_sl_interno_chronos(
    precio_entrada: float,
    direccion: str,
    sl_actual: float,
    edad_seg: float,
    mfe_pct: float,
    tick_size: float,
    trinquete_be_activo: bool = False,
    lambda_wald: float = 0.0,
    vacio_l2_ratio: float = 1.0,
) -> float:
    if trinquete_be_activo or precio_entrada <= 0.0:
        return sl_actual

    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    unwind_base = float(ctrl.get("w4_unwind_seg", 42.0))
    umbral_stall = float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT))

    lam_w = float(lambda_wald or 0.0)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    adelanto_w = 6.0 if lam_w <= -2.00 else (3.0 if lam_w <= -1.20 else 0.0)
    adelanto_v = 4.0 if v_l2 < 0.60 else 0.0
    unwind_seg = max(28.0, unwind_base - adelanto_w - adelanto_v)

    if edad_seg < unwind_seg or mfe_pct >= umbral_stall:
        return sl_actual

    sl_decay_pct = float(ctrl.get("w4_sl_decay_pct", 0.0032))
    sl_base_pct = float(cfg.SL_INTERNO_PCT)
    ventana_comp = max(
        18.0,
        30.0 - (4.0 * max(0.0, -lam_w - 1.0)) - (6.0 * max(0.0, 0.75 - v_l2)),
    )
    progreso_lin = min(1.0, max(0.0, (edad_seg - unwind_seg) / ventana_comp))
    exponente_conv = 0.68 if (lam_w <= -2.00 or v_l2 < 0.60) else 0.85
    progreso_convexo = progreso_lin ** exponente_conv
    dist_pct = sl_base_pct - (progreso_convexo * max(0.0, sl_base_pct - sl_decay_pct))
    t_sz = max(1e-8, float(tick_size))

    if str(direccion).upper() in ("BUY", "LONG"):
        candidato = mcs.cuantizar_tick(precio_entrada * (1.0 - dist_pct), t_sz, modo="floor")
        return max(sl_actual, candidato)
    else:
        candidato = mcs.cuantizar_tick(precio_entrada * (1.0 + dist_pct), t_sz, modo="ceil")
        return min(sl_actual, candidato) if sl_actual > 0.0 else candidato
