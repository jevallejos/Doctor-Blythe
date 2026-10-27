# -*- coding: utf-8 -*-
"""
Micro-Modulo Ofensivo #1: Supervivencia en Cola L1 Moallemi & Yuan (2017)
y Salto Pasivo Penny-Jump con Candado Anti-Sobreprecio.
"""
from typing import Tuple
import config_parametros as cfg


def evaluar_aborto_cola_moallemi(
    direccion: str,
    q_l1_inicial: float,
    q_l1_actual: float,
    ofi_actual: float,
    h_actual: float,
    edad_orden_seg: float,
) -> Tuple[bool, str]:
    """
    Evalua si una orden PostOnly descansando en L1 sufre seleccion adversa real:
    1. La disminucion de Q_L1 (< 30%) SOLO aborta si el flujo OFI es adverso
       (evita cancelar cuando avanzamos al #1 de la fila FIFO con OFI >= 0).
    2. El giro adverso de OFI solo aborta si supera -0.22 (en LONG) o +0.22 (en SHORT),
       y si la liquidez L1 crecio o se mantuvo firme (>= 95%), tolera parpadeos hasta -0.28.
    3. Hurst > 0.495 solo aborta si el flujo OFI NO esta empujando a nuestro favor.
    """
    grace_seg = float(getattr(cfg, "MOALLEMI_MIN_AGE_ABORT_SEG", 0.35))
    if edad_orden_seg < grace_seg:
        return False, "GRACE_WINDOW"

    ratio_min = float(getattr(cfg, "MOALLEMI_QUEUE_DEPLETION_ABORT_RATIO", 0.30))
    ofi_flip_base = float(getattr(cfg, "MOALLEMI_OFI_ADVERSE_ABORT_THRESHOLD", 0.22))
    h_abort = float(getattr(cfg, "MOALLEMI_HURST_ABORT_THRESHOLD", 0.54))

    ratio_cola = (q_l1_actual / q_l1_inicial) if q_l1_inicial > 0.0 else 1.0

    # Presion contraria en el libro
    presion_contra_leve = (
        (direccion == "LONG" and ofi_actual < -0.05)
        or (direccion == "SHORT" and ofi_actual > 0.05)
    )
    # 1. Erosion toxica real: la fila se vacia (< 30%) MIENTRAS presionan en contra,
    #    o colapso extremo (< 12%) de una fila grande (> 1000 contratos)
    cola_erosionada = (q_l1_inicial > 0.0) and (
        (ratio_cola < ratio_min and presion_contra_leve)
        or (q_l1_inicial >= 1000.0 and ratio_cola < 0.12 and ofi_actual <= 0.0)
    )

    # 2. Giro adverso de OFI (si la fila L1 nos respalda >= 95%, exige giro mas fuerte >= 0.28)
    umbral_ofi_efectivo = max(ofi_flip_base, 0.28) if ratio_cola >= 0.95 else max(ofi_flip_base, 0.22)
    ofi_adverso = (
        (direccion == "LONG" and ofi_actual < -umbral_ofi_efectivo)
        or (direccion == "SHORT" and ofi_actual > umbral_ofi_efectivo)
    )

    # 3. Hurst direccional: si OFI empuja a favor (>= +0.08) o la fila crecio, H <= 0.54 es rebote sano
    flujo_a_favor = (
        (direccion == "LONG" and ofi_actual >= 0.08)
        or (direccion == "SHORT" and ofi_actual <= -0.08)
    )
    hurst_toxico = (
        (h_actual > h_abort)
        or (h_actual > 0.495 and not flujo_a_favor and ratio_cola < 0.85)
    )

    if cola_erosionada or ofi_adverso or hurst_toxico:
        return (
            True,
            f"Q_L1={q_l1_actual:.1f}/{q_l1_inicial:.1f}, H={h_actual:.2f}, OFI={ofi_actual:+.2f}",
        )
    return False, "OK"


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
    """
    Penny-Jump con Candado Anti-Sobreprecio (Remediacion Trade #10):
    - Maximo 1 salto (re_pegs_realizados < 1) tras >= 0.85s de reposo en L1.
    - Prohibido saltar si la racha OFI de entrada ya es madura (>= 8 ticks)
      o si 1 tick representa > 0.045% del precio.
    - El nuevo precio jamas puede desplazarse mas de 1.0 tick desde precio_orden.
    """
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
