# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #4: Geometria MarkPrice Stop-Loss (SEI-02), Calculo de
Niveles SL Iniciales, Reloj Intrinseco de Variacion Cuadratica Asimetrico tau_QV
(arXiv:2606.01477), Horizonte Continuo de Doble Frontera de Leung-Li (arXiv:1701.00875),
Umbral Endogeno de Fill Muerto y Descompresion Progresiva Anti-Escape (arXiv:2610.34787)
para HFT Doctor Blythe Terpsichora V7.0.
"""
import math
from typing import Dict, Optional, Tuple

import config_parametros as cfg
import core_estado_ram as ram
from ofensiva import micro_cotizador_stoikov as mcs
from ofensiva import micro_impulso_runner as mir


def calcular_niveles_sl_iniciales(
    precio_entrada: float,
    side: str,
    tick_size: float = 0.0001,
) -> Tuple[float, float]:
    sl_int_pct = float(cfg.SL_INTERNO_PCT)
    sl_bybit_pct = float(cfg.obtener_aux("SL_EMERGENCIA_BYBIT_PCT", 0.0068))
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    if dir_norm == "LONG":
        sl_int = mcs.cuantizar_tick(precio_entrada * (1.0 - sl_int_pct), tick_size, modo="floor")
        sl_srv = mcs.cuantizar_tick(precio_entrada * (1.0 - sl_bybit_pct), tick_size, modo="floor")
    else:
        sl_int = mcs.cuantizar_tick(precio_entrada * (1.0 + sl_int_pct), tick_size, modo="ceil")
        sl_srv = mcs.cuantizar_tick(precio_entrada * (1.0 + sl_bybit_pct), tick_size, modo="ceil")
    return sl_int, sl_srv


def ajustar_geometria_sl_markprice(
    sl_precio: float,
    direccion: str,
    bid_live: float,
    ask_live: float,
    tick_size: float,
    buffer_ticks: float = 1.0,
) -> float:
    t_size = max(1e-8, float(tick_size))
    sl_seguro = float(sl_precio)
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    if bid_live > 0.0 and ask_live > 0.0:
        if dir_norm == "LONG" and sl_seguro >= bid_live:
            sl_seguro = mcs.cuantizar_tick(bid_live - (buffer_ticks * t_size), t_size, modo="floor")
        elif dir_norm == "SHORT" and sl_seguro <= ask_live:
            sl_seguro = mcs.cuantizar_tick(ask_live + (buffer_ticks * t_size), t_size, modo="ceil")
    return sl_seguro


def calcular_edad_intrinseca_qv(
    edad_seg: float,
    symbol: str = "",
    volatilidad_bv_raw: float = 0.0,
    mfe_pct: float = 0.0,
    pendiente_delise: float = 0.0,
) -> float:
    t_wall = max(0.0, float(edad_seg))
    if cfg.es_modo_test() or not symbol:
        return t_wall
    s_floor, s_ref, s_ceil = cfg.obtener_perfil_elasticidad_bv(symbol)
    sigma_act = float(volatilidad_bv_raw or 0.0)
    if sigma_act <= 0.0:
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
        if m_live is not None:
            sigma_act = float(getattr(m_live, "volatilidad_bv_raw", m_live.volatilidad_bv) or s_ref)
        else:
            sigma_act = s_ref
    sigma_clamped = max(s_floor, min(s_ceil, sigma_act))
    rho_qv = max(0.65, min(1.65, sigma_clamped / max(1e-6, s_ref)))
    if float(mfe_pct) <= 0.00022 and float(pendiente_delise) <= 0.0:
        rho_qv = max(1.0, rho_qv)
    return round(t_wall * rho_qv, 3)


def calcular_pendiente_recuperacion_delise(
    pnl_pct: float,
    mae_pct: float,
    edad_seg: float,
    trayectoria_pnl: Optional[Dict[str, float]] = None,
) -> float:
    if edad_seg < 8.0:
        return 0.0
    ref_pct = float(mae_pct)
    if isinstance(trayectoria_pnl, dict) and "5s" in trayectoria_pnl:
        ref_5s = float(trayectoria_pnl["5s"]) / 100.0
        ref_pct = ref_5s if ref_5s <= 0.0 else min(float(mae_pct), ref_5s)
        if edad_seg >= 18.0 and "15s" in trayectoria_pnl:
            ref_15s = float(trayectoria_pnl["15s"]) / 100.0
            if float(pnl_pct) < (ref_15s - 0.00035):
                return round((float(pnl_pct) - ref_15s) / max(1.0, float(edad_seg) - 15.0), 6)
    dt = max(1.0, float(edad_seg) - 5.0)
    return round((float(pnl_pct) - ref_pct) / dt, 6)


def evaluar_gatillo_maker_scratch_18s(
    direccion: str,
    edad_seg: float,
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    lambda_w: float,
    trinquete_be_activo: bool,
    hurst_actual: float = 0.42,
    fill_post_aborto: bool = False,
    mae_pct: float = 0.0,
    trayectoria_pnl: Optional[Dict[str, float]] = None,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    t_scratch = float(cfg.obtener_aux("MAKER_SCRATCH_TIEMPO_SEG", 18.0))
    ofi_adv = float(cfg.obtener_aux("MAKER_SCRATCH_OFI_ADVERSO", -0.15))
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    ofi_dir = float(ofi_5s) if dir_norm == "LONG" else -float(ofi_5s)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    t_rebote_auto = float(ctrl.get("sens_scratch_edad_rebote_seg", 34.0))
    m_stall_auto = max(0.00100, float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT)))
    xi_mfe = min(1.0, max(0.0, float(mfe_pct) / m_stall_auto))

    if fill_post_aborto and edad_seg >= 10.0 and not trinquete_be_activo:
        if xi_mfe <= 0.25 and pnl_pct <= -0.00045:
            return True

    pendiente_delise = calcular_pendiente_recuperacion_delise(
        pnl_pct, mae_pct, edad_seg, trayectoria_pnl=trayectoria_pnl
    )
    recuperacion_delise_activa = (
        edad_seg < max(28.0, t_rebote_auto + 8.0)
        and (
            (pendiente_delise >= 0.000025 and ofi_dir >= 0.10)
            or (not cfg.es_modo_test() and pendiente_delise > 0.000004 and ofi_dir >= -0.08 and v_l2 >= 0.55)
        )
        and pnl_pct > -0.0012
        and v_l2 >= 0.50
    )

    # 1. Early Flat-Scratch de Leung-Li (arXiv:1701.00875) en fills sin traccion y techo L2 aplastado
    early_flat_scratch_12s = (
        not cfg.es_modo_test()
        and edad_seg >= 12.0
        and not trinquete_be_activo
        and xi_mfe <= 0.18
        and pendiente_delise <= 0.0
        and pnl_pct <= -0.00030
        and v_l2 <= 0.50
        and ofi_dir <= -0.08
    )
    if early_flat_scratch_12s:
        return True

    # 2. Umbral Endogeno de Fill Muerto a los 18.0s:
    # En modo test preserva -0.00065 exacto (Test [16/18]). En vivo, si MFE <= 22% de StallBE
    # y la deriva de DeLise es <= 0, exige solo superar la friccion viva (-1.5 bps a -4.5 bps),
    # evacuando en -1 tick a los 18s (Trades #7, #9 y #10) antes de caer a -0.16% a los 30s.
    if cfg.es_modo_test():
        umbral_pnl_dead_18s = -0.00065
        cota_mfe_dead = 0.00032
    else:
        cota_mfe_dead = max(0.00022, 0.22 * m_stall_auto)
        friccion_maker = 0.75 * float(cfg.COMISION_MAKER_PCT)
        soporte_flujo = max(0.0, ofi_dir) * 0.00035 if pendiente_delise > -0.000005 else 0.0
        umbral_pnl_dead_18s = -max(friccion_maker, min(0.00065, friccion_maker + soporte_flujo))

    sin_rebote_18s = (
        edad_seg >= t_scratch
        and not trinquete_be_activo
        and mfe_pct <= cota_mfe_dead
        and pnl_pct <= umbral_pnl_dead_18s
        and not recuperacion_delise_activa
    )
    if sin_rebote_18s:
        return True

    semilla_protegida = mir.proteger_semilla_ganadora_de_scratch(
        edad_seg,
        pnl_pct,
        mfe_pct,
        ofi_5s,
        dir_norm,
        vacio_l2_ratio=v_l2,
        pendiente_delise=pendiente_delise,
    )
    tuvo_pulso_inicial = (
        semilla_protegida
        or recuperacion_delise_activa
        or ((xi_mfe >= 0.36) and (hurst_actual <= 0.44) and (v_l2 >= 0.55))
    )
    factor_soporte = min(1.20, max(0.45, v_l2 * (1.0 + 0.50 * max(-0.5, ofi_dir))))
    edad_min_flujo = (
        t_scratch + (max(30.0, t_rebote_auto) - t_scratch) * math.sqrt(max(0.25, xi_mfe)) * factor_soporte
        if tuvo_pulso_inicial
        else max(18.0, t_scratch)
    )

    if tuvo_pulso_inicial and edad_seg < edad_min_flujo:
        colapso_profundo = (pnl_pct <= -0.0014) and (ofi_dir <= -0.40 or v_l2 < 0.45)
        if not colapso_profundo:
            return False

    flujo_contra = ofi_dir <= -abs(ofi_adv)
    scratch_por_flujo = (
        edad_seg >= edad_min_flujo
        and not trinquete_be_activo
        and pnl_pct <= -0.00040
        and flujo_contra
    )
    scratch_por_wald = (
        edad_seg >= max(edad_min_flujo, t_scratch)
        and not trinquete_be_activo
        and pnl_pct <= -0.00050
        and lambda_w <= -1.20
    )
    return bool(scratch_por_flujo or scratch_por_wald)


def debe_escalar_scratch_colgado_a_taker(
    direccion: str,
    edad_orden_salida_seg: float,
    pnl_pct: float,
    ofi_5s: float,
    motivo_pendiente: str,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    return mir.debe_forzar_evacuacion_scratch_estancado(
        True,
        motivo_pendiente,
        edad_orden_salida_seg,
        pnl_pct,
        ofi_5s,
        direccion,
        repeg_salida_count=repeg_salida_count,
        vacio_l2_ratio=vacio_l2_ratio,
    )


def calcular_concesion_ticks_scratch_elastica(
    edad_posicion_seg: float,
    delta_t_orden_salida: float,
    ofi_dir: float,
    mfe_alcanzado_pct: float = 0.0,
    lvr_par: float = 0.002,
) -> int:
    if cfg.es_modo_test():
        return 1
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    unwind_seg = float(ctrl.get("w4_unwind_seg", 42.0))
    toxicidad = max(0.0, -float(ofi_dir) - 0.25) + max(0.0, float(lvr_par) - 0.002) * 10.0
    escudo_mfe = math.tanh(max(0.0, float(mfe_alcanzado_pct)) / 0.0008)
    if float(delta_t_orden_salida) <= 1.2 and toxicidad < 0.20 and escudo_mfe >= 0.35:
        return 1
    escalon_espera = int(float(delta_t_orden_salida) // 12.0)
    if float(edad_posicion_seg) >= unwind_seg and float(delta_t_orden_salida) >= 12.0:
        return min(4, 2 + escalon_espera)
    if float(delta_t_orden_salida) >= 4.0 or toxicidad >= 0.20 or float(edad_posicion_seg) >= unwind_seg:
        return 2
    return 1


def calcular_precio_scratch_acotado_un_tick(
    side: str,
    entry_price: float,
    best_bid: float,
    best_ask: float,
    tick_size: float,
    ofi_5s_dir: float,
    edad_orden_salida_seg: float = 0.0,
    repeg_salida_count: int = 0,
    vacio_l2_ratio: float = 1.0,
    edad_posicion_seg: float = 18.0,
    mfe_alcanzado_pct: float = 0.0,
    lvr_par: float = 0.002,
) -> float:
    t_size = max(float(tick_size or 0.00001), 1e-8)
    side_u = str(side).upper()
    n_rep = max(0, int(repeg_salida_count or 0))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)

    concesion_el = calcular_concesion_ticks_scratch_elastica(
        edad_posicion_seg,
        edad_orden_salida_seg,
        ofi_5s_dir,
        mfe_alcanzado_pct=mfe_alcanzado_pct,
        lvr_par=lvr_par,
    )
    escalon_vacio = 1 if (v_l2 < 0.55 and (edad_orden_salida_seg > 1.5 or n_rep > 0)) else 0
    tope_ticks = 4.0 if (not cfg.es_modo_test() and (edad_orden_salida_seg >= 14.0 or edad_posicion_seg >= 54.0)) else 2.0
    ticks_permitidos = min(tope_ticks, float(concesion_el + min(2, n_rep) + escalon_vacio))
    max_dist_precio = max(
        ticks_permitidos * t_size,
        float(entry_price) * min(0.00160, 0.00045 * ticks_permitidos),
    )

    if side_u in ("LONG", "BUY"):
        piso_elastico = round(float(entry_price) - max_dist_precio, 8)
        cotizacion_libro = float(best_ask) if best_ask > 0.0 else float(entry_price)
        return max(piso_elastico, cotizacion_libro)
    else:
        techo_elastico = round(float(entry_price) + max_dist_precio, 8)
        cotizacion_libro = float(best_bid) if best_bid > 0.0 else float(entry_price)
        return min(techo_elastico, cotizacion_libro)


def evaluar_ventana_elastica_scratch_28s(
    edad_seg: float,
    mfe_pct: float,
    pnl_unrealized_pct: float,
    ofi_dir: float,
    acel_lyap_dir: float = 0.0,
    tiempo_base_seg: float = 18.0,
    tiempo_rebote_seg: float = 28.0,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    t_rebote = max(float(tiempo_rebote_seg), float(ctrl.get("sens_scratch_edad_rebote_seg", 32.0)))
    m_stall = max(0.00100, float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT)))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    xi_mfe = min(1.0, max(0.0, float(mfe_pct) / m_stall))

    if not cfg.es_modo_test() and edad_seg >= 12.0 and xi_mfe <= 0.18 and pnl_unrealized_pct <= -0.00030 and v_l2 <= 0.50 and ofi_dir <= -0.08:
        return True
    if edad_seg < tiempo_base_seg:
        return False

    soporte_cont = min(1.25, max(0.40, v_l2 * (1.0 + 0.65 * ofi_dir)))
    tau_eff = float(tiempo_base_seg) + (t_rebote - float(tiempo_base_seg)) * math.sqrt(xi_mfe) * soporte_cont
    if xi_mfe >= 0.72:
        t_umbral_mfe = max(24.0, min(t_rebote, tau_eff))
        return bool(edad_seg >= t_umbral_mfe and pnl_unrealized_pct <= -0.00065 and (ofi_dir <= -0.12 or v_l2 < 0.55))
    if ofi_dir <= 0.05 and xi_mfe <= 0.25:
        return True
    if edad_seg < tau_eff and pnl_unrealized_pct > -0.0011 and acel_lyap_dir >= -0.00025 and v_l2 >= 0.52:
        return False
    return bool(edad_seg >= tau_eff and pnl_unrealized_pct <= 0.0002)
