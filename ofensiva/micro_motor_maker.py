# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #1: Supervivencia en Cola L1 Moallemi & Yuan (2017),
Carrera de Tiempos de Primer Paso (Muerte Pura vs Nacimiento-Muerte, arXiv:2403.02572v2)
y Salto Pasivo Penny-Jump con Candado Anti-Sobreprecio.
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


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
) -> Tuple[bool, bool]:
    """
    Evalua si una orden PostOnly descansando en L1 sufre seleccion adversa real.
    Integra la carrera de tiempos de primer paso (arXiv:2403.02572v2 & arXiv:2306.05479)
    entre la tasa de vaciado propia (mu_own) y la opuesta (mu_opp).
    Retorna (cola_toxica: bool, erosion_adversa: bool).
    """
    if veto_btc_activo:
        return True, False

    grace_seg = float(getattr(cfg, "MOALLEMI_MIN_AGE_ABORT_SEG", 0.35))
    if edad_orden_seg < grace_seg:
        return False, False

    ctrl = getattr(ram.ESTADO_GLOBAL, "controlador_autonomo", {}) or {}
    hold_ratio_dyn = float(ctrl.get("sens_q_l1_hold_ratio", 0.55))
    ofi_abort_dyn = abs(float(ctrl.get("sens_ofi_abort_cola", -0.35)))

    ratio_min = float(getattr(cfg, "MOALLEMI_QUEUE_DEPLETION_ABORT_RATIO", 0.30))
    ofi_flip_base = max(0.22, min(0.42, ofi_abort_dyn * 0.70))
    h_abort = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.54))

    ratio_cola = (q_l1_actual / q_l1_inicial) if q_l1_inicial > 0.0 else 1.0
    dt_eff = max(0.05, float(edad_orden_seg))

    presion_contra_leve = (
        (direccion == "LONG" and ofi_actual < -0.05)
        or (direccion == "SHORT" and ofi_actual > 0.05)
    )

    # Mejora #1 (arXiv:2403.02572v2): Carrera de Tiempos de Primer Paso (mu_own vs mu_opp)
    # Solo activa aborto en la zona gris (ratio_cola <= hold_ratio_dyn) cuando OFI pierde traccion
    # y nuestra fila se vacia > 2.5x mas rapido que la punta opuesta mientras la opuesta se engrosa.
    carrera_primer_paso_adversa = False
    if q_l1_inicial > 0.0 and q_opp_inicial > 0.0 and ratio_cola <= hold_ratio_dyn:
        mu_own = max(0.0, q_l1_inicial - q_l1_actual) / dt_eff
        mu_opp = max(0.0, q_opp_inicial - q_opp_actual) / dt_eff
        opp_engrosando = q_opp_actual >= (q_opp_inicial * 1.05)
        ofi_sin_traccion = (
            (direccion == "LONG" and ofi_actual < 0.0)
            or (direccion == "SHORT" and ofi_actual > 0.0)
        )
        if opp_engrosando and ofi_sin_traccion and mu_own > (2.5 * max(1e-6, mu_opp)):
            carrera_primer_paso_adversa = True

    cola_erosionada = (q_l1_inicial > 0.0) and (
        (ratio_cola < ratio_min and presion_contra_leve)
        or (q_l1_inicial >= 1000.0 and ratio_cola < 0.12 and ofi_actual <= 0.0)
        or carrera_primer_paso_adversa
    )

    umbral_ofi_efectivo = max(ofi_flip_base, 0.28) if ratio_cola >= 0.95 else max(ofi_flip_base, 0.22)
    ofi_adverso = (
        (direccion == "LONG" and ofi_actual < -umbral_ofi_efectivo)
        or (direccion == "SHORT" and ofi_actual > umbral_ofi_efectivo)
    )

    flujo_a_favor = (
        (direccion == "LONG" and ofi_actual >= 0.08)
        or (direccion == "SHORT" and ofi_actual <= -0.08)
    )
    hurst_toxico = (
        (h_actual > h_abort)
        or (h_actual > 0.495 and not flujo_a_favor and ratio_cola < 0.85)
    )

    if cola_erosionada or ofi_adverso or hurst_toxico:
        return True, bool(cola_erosionada)
    return False, False


def listo_para_repeg_cola(
    fue_cancelada_postonly: bool,
    elapsed_seg: float,
    ultimo_repeg_elapsed_seg: float,
) -> bool:
    if fue_cancelada_postonly:
        return True
    intervalo = max(0.25, float(getattr(cfg, "REPEG_PASIVO_ENTRADA_SEG", 0.65)))
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
) -> Tuple[bool, float]:
    if not bool(getattr(cfg, "PENNY_JUMP_HABILITADO", True)):
        return False, precio_orden
    if re_pegs_realizados >= 1 or tick_size <= 0.0 or precio_orden <= 0.0:
        return False, precio_orden
    if edad_en_nivel_seg < 0.85:
        return False, precio_orden
    if ofi_ticks_racha >= 8:
        return False, precio_orden
    if (tick_size / precio_orden) > 0.00045:
        return False, precio_orden

    h_max = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.485))
    if h_actual >= h_max:
        return False, precio_orden

    spread = ask_actual - bid_actual
    if spread <= 0.0:
        return False, precio_orden

    if direccion == "LONG":
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

# === [TERPSICHORA-QUEUE-HOLD-GUARD-V1] ===
def debe_proteger_orden_en_cola_por_flujo_favorable(
    q_ratio: float,
    ofi_dir: float,
    hurst: float,
    min_q_floor: float = 0.22,
) -> bool:
    """
    Inhibe Early Queue Abort cuando el OFI direccional es fuertemente favorable
    (>= +0.10) y el Hurst se mantiene anti-persistente (<= 0.490), evitando
    cancelar tiros ganadores en < 2.5s por oscilaciones normales de L1.
    """
    if hurst > 0.495:
        return False
    if ofi_dir >= 0.10 and q_ratio >= min(0.15, min_q_floor):
        return True
    return bool(q_ratio >= min_q_floor and ofi_dir >= -0.48)
