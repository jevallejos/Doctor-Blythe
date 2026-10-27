# -*- coding: utf-8 -*-
"""
Micro-Modulo Independiente de Supervivencia en Cola L1 y Re-Peg Maker (Moallemi-Stoikov).
Evita abortar ordenes PostOnly cuando Hurst sube por el propio rebote a favor (OFI >= +0.12)
y regula la cadencia de Queue-Jump para no agotar los 2 re-pegs prematuramente.
"""
from typing import Tuple
import config_parametros as cfg


def evaluar_aborto_cola_moallemi(
    direccion: str,
    q_l1_init: float,
    q_l1_now: float,
    ofi_profundo: float,
    hurst_actual: float,
    elapsed_seg: float,
    veto_btc_activo: bool,
) -> Tuple[bool, bool]:
    """
    Retorna (cola_toxica: bool, erosion_adversa: bool).
    Si el flujo OFI empuja claramente a favor de nuestra orden (>= +0.12 en LONG o <= -0.12 en SHORT),
    no aborta por subida de Hurst, permitiendo capturar el fill del rebote en V.
    """
    erosion_adversa = (
        q_l1_init > 0.0
        and q_l1_now > 0.0
        and (q_l1_now / q_l1_init) < 0.15
        and (
            (direccion == "LONG" and ofi_profundo <= -0.10)
            or (direccion == "SHORT" and ofi_profundo >= 0.10)
        )
    )

    flujo_a_favor_fuerte = (
        (direccion == "LONG" and ofi_profundo >= 0.12)
        or (direccion == "SHORT" and ofi_profundo <= -0.12)
    )
    hurst_toxico = (hurst_actual > cfg.HURST_TECHO_DURO_ABSOLUTO) and (not flujo_a_favor_fuerte)

    ofi_contra_fuerte = (
        (direccion == "LONG" and ofi_profundo <= -0.25)
        or (direccion == "SHORT" and ofi_profundo >= 0.25)
    )

    cola_toxica = erosion_adversa or (
        elapsed_seg >= cfg.EARLY_QUEUE_ABORT_SEG
        and (hurst_toxico or veto_btc_activo or ofi_contra_fuerte)
    )
    return bool(cola_toxica), bool(erosion_adversa)


def listo_para_repeg_cola(
    fue_cancelada_postonly: bool,
    elapsed_seg: float,
    ultimo_repeg_elapsed: float,
) -> bool:
    """
    Si Bybit rechazo/cancelo por PostOnly, re-cotiza de inmediato.
    Si la orden sigue viva descansando en el libro, espera al menos 0.45s entre saltos
    para conservar prioridad de cola L1 y no quemar los 2 re-pegs en 0.7s.
    """
    if fue_cancelada_postonly:
        return True
    intervalo_min = max(0.45, float(getattr(cfg, "REPEG_PASIVO_ENTRADA_SEG", 0.65)) * 0.70)
    return bool(elapsed_seg >= 0.35 and (elapsed_seg - ultimo_repeg_elapsed) >= intervalo_min)
