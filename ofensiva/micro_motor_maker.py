# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #1: Supervivencia en Cola L1 Moallemi & Yuan (2017),
Probabilidad Markoviana de Primer Paso de Cont & de Larrard (arXiv:1104.4596),
Densidad de Reposicion de Cola (arXiv:2610.34787), Carrera FPT (arXiv:2403.02572v2),
Blindaje de Climax de Frenado (imb_dir > -0.55, Lyap_dir > 0, FPT < 1.0) y
Salto Pasivo Penny-Jump Sincronizado en Fase para HFT Doctor Blythe Terpsichora V7.0.
"""
import math
from typing import Tuple

import config_parametros as cfg
import core_estado_ram as ram


def debe_proteger_orden_en_cola_por_flujo_favorable(
    q_ratio: float,
    ofi_dir: float,
    hurst: float,
    min_q_floor: float = 0.22,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    if hurst > 0.495 or float(vacio_l2_ratio or 1.0) < 0.50:
        return False
    if ofi_dir >= 0.10 and q_ratio >= max(0.28, min_q_floor):
        return True
    return bool(q_ratio >= max(0.45, min_q_floor) and ofi_dir >= 0.02)


def evaluar_aborto_cola_moallemi(
    direccion: str,
    q_l1_inicial: float,
    q_l1_actual: float,
    ofi_actual: float,
    h_actual: float,
    edad_orden_seg: float,
    veto_btc_activo: bool = False,
    q_opp_inicial: float = 0.0,
    q_opp_actual: float = 0.0,
    cancel_net_l1: float = 0.0,
    imb_l1: float = 0.0,
    vacio_l2_ratio: float = 1.0,
    z_score_actual: float = 0.0,
    aceleracion_lyapunov: float = 0.0,
    hawkes_actual: float = 0.0,
) -> Tuple[bool, bool]:
    """
    Evalua si una orden PostOnly descansando en L1 sufre seleccion adversa real:
    1. En presencia de veto_btc_activo, preserva la orden si:
       a) Ya gano prioridad con reposicion institucional fuerte (q_ratio >= 1.02, fpt < 0.50), o
       b) Esta en Climax de Frenado en V (|Z| >= 3.20, ofi_dir >= 0.75, lyap_dir > 0,
          imb_dir > -0.55, fpt < 1.0, q_ratio >= 0.50), evitando abortar rebotes explosivos
          como el de ZEREBRO +0.4984% sin comprometer los salvamentos reales (imb_dir <= -0.55).
    2. Evalua la probabilidad Markoviana de Cont-de Larrard P_Cont = q_own / (q_own + q_opp)
       (arXiv:1104.4596) acoplada a la compresion de vacio profundo L2.
    3. Evalua carrera FPT (arXiv:2403.02572v2) y retirada agresiva L1 (arXiv:2502.17417).
    """
    ratio_cola = (q_l1_actual / q_l1_inicial) if q_l1_inicial > 0.0 else 1.0
    dir_norm = "LONG" if str(direccion).upper() in ("BUY", "LONG") else "SHORT"
    signo_dir = 1.0 if dir_norm == "LONG" else -1.0
    ofi_dir = signo_dir * float(ofi_actual)
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    dt_eff = max(0.05, float(edad_orden_seg))

    merma_rel_own = (max(0.0, q_l1_inicial - q_l1_actual) / q_l1_inicial) if q_l1_inicial > 0.0 else 0.0
    drain_rel_opp = (max(0.0, q_opp_inicial - q_opp_actual) / q_opp_inicial) if q_opp_inicial > 0.0 else 0.0
    fpt_race_ratio = (
        min(10.0, (merma_rel_own / dt_eff) / max(0.02, drain_rel_opp / dt_eff))
        if (q_l1_inicial > 0.0 and q_opp_inicial > 0.0)
        else 1.0
    )

    cancel_dir = signo_dir * float(cancel_net_l1 or 0.0)
    imb_dir = signo_dir * float(imb_l1 or 0.0)
    z_dir = -float(z_score_actual or 0.0) if dir_norm == "LONG" else float(z_score_actual or 0.0)
    lyap_dir = signo_dir * float(aceleracion_lyapunov or 0.0)
    hawkes_dir = signo_dir * float(hawkes_actual or 0.0)

    punta_sana = (imb_dir > -0.55) and (cancel_dir > -0.35)
    climax_frenado_v = (
        not cfg.es_modo_test()
        and punta_sana
        and z_dir >= 3.20
        and ofi_dir >= 0.75
        and hawkes_dir >= 0.50
        and lyap_dir > 0.00005
        and h_actual <= 0.45
        and v_l2 >= 0.58
        and ratio_cola >= 0.50
        and fpt_race_ratio < 1.0
    )
    reposicion_fpt_favorable = (
        not cfg.es_modo_test()
        and punta_sana
        and ratio_cola >= 1.02
        and fpt_race_ratio < 0.50
        and ofi_dir >= 0.30
        and hawkes_dir >= 0.12
        and lyap_dir > 0.00005
        and h_actual <= 0.44
        and v_l2 >= 0.60
    )

    if veto_btc_activo:
        cola_blindada_reposicion = (
            not cfg.es_modo_test()
            and (
                (ratio_cola >= 1.15 and ofi_dir >= 0.60 and h_actual <= 0.42 and v_l2 >= 0.70 and punta_sana)
                or climax_frenado_v
                or reposicion_fpt_favorable
            )
        )
        if not cola_blindada_reposicion:
            return True, False

    grace_seg = float(getattr(cfg, "MOALLEMI_MIN_AGE_ABORT_SEG", 0.35))
    if edad_orden_seg < grace_seg:
        return False, False

    if climax_frenado_v or reposicion_fpt_favorable:
        return False, False

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    hold_ratio_dyn = float(ctrl.get("sens_q_l1_hold_ratio", 0.55))
    ofi_abort_dyn = abs(float(ctrl.get("sens_ofi_abort_cola", -0.35)))

    ratio_min = float(getattr(cfg, "MOALLEMI_QUEUE_DEPLETION_ABORT_RATIO", 0.30))
    ofi_flip_base = max(0.22, min(0.42, ofi_abort_dyn * 0.70))
    h_abort = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.54))
    presion_contra_leve = ofi_dir < -0.05

    carrera_primer_paso_adversa = False
    if q_l1_inicial > 0.0 and q_opp_inicial > 0.0 and ratio_cola <= max(0.65, hold_ratio_dyn):
        crec_rel_opp = (q_opp_actual - q_opp_inicial) / q_opp_inicial
        if (
            merma_rel_own >= 0.30
            and crec_rel_opp >= 0.05
            and ofi_dir < 0.0
            and fpt_race_ratio > 2.0
        ):
            carrera_primer_paso_adversa = True

    prob_cont_larrard = (
        (q_l1_actual / max(1e-9, q_l1_actual + q_opp_actual))
        if (q_l1_actual > 0.0 and q_opp_actual > 0.0)
        else 0.50
    )
    compresion_cont_l2 = (
        not cfg.es_modo_test()
        and edad_orden_seg >= 1.10
        and v_l2 < 0.36
        and prob_cont_larrard < 0.22
        and ofi_dir < 0.08
    )

    retirada_l1_adversa = (
        ratio_cola <= 0.72
        and cancel_dir <= -0.52
        and imb_dir <= -0.58
        and ofi_dir <= 0.0
    )

    cola_erosionada = (q_l1_inicial > 0.0) and (
        (ratio_cola < ratio_min and presion_contra_leve)
        or (q_l1_inicial >= 1000.0 and ratio_cola < 0.12 and ofi_dir <= 0.0)
        or carrera_primer_paso_adversa
        or retirada_l1_adversa
        or compresion_cont_l2
    )
    umbral_ofi_efectivo = max(ofi_flip_base, 0.28) if ratio_cola >= 0.95 else max(ofi_flip_base, 0.22)
    ofi_adverso = ofi_dir < -umbral_ofi_efectivo
    flujo_a_favor = ofi_dir >= 0.08
    hurst_toxico = (
        (h_actual > h_abort)
        or (h_actual > 0.495 and not flujo_a_favor and ratio_cola < 0.85)
    )

    if not cola_erosionada and not hurst_toxico and debe_proteger_orden_en_cola_por_flujo_favorable(
        ratio_cola, ofi_dir, h_actual, min_q_floor=hold_ratio_dyn, vacio_l2_ratio=v_l2
    ):
        return False, False

    if cola_erosionada or ofi_adverso or hurst_toxico:
        return True, bool(cola_erosionada)
    return False, False


def listo_para_repeg_cola(
    fue_cancelada_postonly: bool,
    elapsed_seg: float,
    ultimo_repeg_elapsed_seg: float,
    vacio_l2_ratio: float = 1.0,
) -> bool:
    if fue_cancelada_postonly:
        return True
    intervalo_base = max(0.25, float(getattr(cfg, "REPEG_PASIVO_ENTRADA_SEG", 0.65)))
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    factor_vacio = 0.85 if v_l2 >= 1.35 else 1.0
    intervalo = max(0.25, round(intervalo_base * factor_vacio, 3))
    return bool((elapsed_seg - ultimo_repeg_elapsed_seg) >= intervalo)


def evaluar_salto_punta_penny(
    direccion: str,
    precio_orden: float,
    bid_actual: float,
    ask_actual: float,
    tick_size: float,
    ofi_actual: float,
    h_actual: float,
    re_pegs_realizados: int,
    edad_en_nivel_seg: float = 1.0,
    ofi_ticks_racha: int = 0,
    vacio_l2_ratio: float = 1.0,
    ofi_inicial: float = 0.0,
    q_ratio: float = 1.0,
    lvr_par: float = 0.002,
) -> Tuple[bool, float]:
    if not bool(getattr(cfg, "PENNY_JUMP_HABILITADO", True)):
        return False, precio_orden
    if re_pegs_realizados >= 1 or tick_size <= 0.0 or precio_orden <= 0.0:
        return False, precio_orden
    v_l2 = float(vacio_l2_ratio if vacio_l2_ratio is not None else 1.0)
    edad_min_penny = (
        0.85
        if cfg.es_modo_test()
        else max(0.45, min(0.65, float(getattr(cfg, "REPEG_PASIVO_ENTRADA_SEG", 0.65)) * (0.85 if v_l2 >= 1.25 else 0.95)))
    )
    if edad_en_nivel_seg < edad_min_penny:
        return False, precio_orden
    if ofi_ticks_racha >= 8:
        return False, precio_orden
    if (tick_size / precio_orden) > 0.00045:
        return False, precio_orden
    if v_l2 < 0.55:
        return False, precio_orden
    h_max = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.485))
    if h_actual >= h_max:
        return False, precio_orden

    spread = ask_actual - bid_actual
    if spread <= 0.0:
        return False, precio_orden

    es_long_dir = str(direccion).upper() in ("BUY", "LONG")
    ok_deriv_ofi = autorizar_repeg_con_derivada_ofi(
        ofi_actual,
        ofi_inicial if ofi_inicial != 0.0 else ofi_actual,
        edad_en_nivel_seg,
        q_ratio,
        es_long_dir,
        lvr_par=lvr_par,
    )
    if not cfg.es_modo_test() and not ok_deriv_ofi:
        return False, precio_orden

    if es_long_dir:
        if bid_actual > (precio_orden + 0.5 * tick_size) and ofi_actual >= 0.35:
            candidato = min(bid_actual, ask_actual - tick_size, precio_orden + tick_size)
            if candidato > precio_orden:
                return True, round(candidato, 8)
    else:
        if ask_actual < (precio_orden - 0.5 * tick_size) and ofi_actual <= -0.35:
            candidato = max(ask_actual, bid_actual + tick_size, precio_orden - tick_size)
            if candidato < precio_orden:
                return True, round(candidato, 8)
    return False, precio_orden


def autorizar_repeg_con_derivada_ofi(
    ofi_actual: float,
    ofi_inicial: float,
    dt_seg: float,
    q_ratio: float,
    es_long: bool,
    lvr_par: float = 0.002,
) -> bool:
    ofi_dir_now = float(ofi_actual) if es_long else -float(ofi_actual)
    ofi_dir_init = float(ofi_inicial) if es_long else -float(ofi_inicial)
    dt_clean = max(0.10, float(dt_seg))
    umbral_ofi = 0.45 + min(0.22, float(lvr_par) * 25.0)
    umbral_q = 0.40 + min(0.20, float(lvr_par) * 20.0)
    if not cfg.es_modo_test() and ofi_dir_init >= 0.70:
        ref_init = max(umbral_ofi, ofi_dir_init * math.exp(-dt_clean / 1.25))
        d_ofi_dt = (ofi_dir_now - min(ofi_dir_init, ref_init)) / dt_clean
        if ofi_dir_now >= max(0.65, umbral_ofi + 0.15):
            umbral_q = min(umbral_q, 0.24)
    else:
        d_ofi_dt = (ofi_dir_now - ofi_dir_init) / dt_clean
    return bool(ofi_dir_now >= umbral_ofi and d_ofi_dt >= -0.12 and float(q_ratio) >= umbral_q)
