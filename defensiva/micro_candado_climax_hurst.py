# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #6: Candado Fisico Anti-Override de Hurst en SHORT-SNIPER,
Discriminador Termodinamico de Irreversibilidad LOB (arXiv:2610.16151) y
Gobernador Elastico de Enfriamiento Post-Hurst para HFT Doctor Blythe Terpsichora V7.0.
"""
from typing import Tuple
import config_parametros as cfg
import core_estado_ram as ram


def evaluar_tope_duro_climax_hurst(
    z_score: float,
    hurst_actual: float,
    ofi_actual: float,
    aceleracion_lyapunov: float,
    hurst_cap_base: float = 0.485,
    techo_duro_absoluto: float = 0.515,
    irreversibilidad_lob: float = 0.0,
    cancel_net_l1: float = 0.0,
) -> Tuple[bool, float, str]:
    """
    Evalua si un disparo SHORT-SNIPER cumple la barrera fractal de Hurst:
    - Regla base: H <= hurst_cap_base (0.485).
    - Si sens_climax_hurst_override esta activo, hay climax extremo (Z >= +5.20,
      OFI <= ofi_req_climax, Lyapunov <= -0.00050) y la produccion de entropia
      direccional no indica cascada alcista irreversible (irreversibilidad_lob <= 0.88),
      permite un margen maximo hasta 0.515.
    - JAMAS permite vender en corto si H > 0.515.
    """
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    override_activo = float(ctrl.get("sens_climax_hurst_override", 1.0)) >= 0.5
    irrev = float(irreversibilidad_lob or 0.0)

    if hurst_actual <= hurst_cap_base:
        return True, hurst_cap_base, "OK"

    if hurst_actual > techo_duro_absoluto or irrev > 0.88:
        return False, hurst_cap_base, f"H={hurst_actual:.3f}>{hurst_cap_base:.3f}"

    penal_irrev = 0.12 * max(0.0, irrev - 0.55)
    penal_cancel = 0.06 * max(0.0, float(cancel_net_l1 or 0.0) - 0.35)
    ofi_req_climax = -min(0.95, 0.80 + penal_irrev + penal_cancel)

    climax_agotado = (
        override_activo
        and z_score >= 5.20
        and ofi_actual <= ofi_req_climax
        and aceleracion_lyapunov <= -0.00050
    )
    if climax_agotado:
        return True, techo_duro_absoluto, "CLIMAX_HURST_CAPPED_OK"

    return False, hurst_cap_base, f"H={hurst_actual:.3f}>{hurst_cap_base:.3f}"


def verificar_enfriamiento_post_hurst_short(
    ahora_ts: float,
    ultimo_hurst_alto_ts: float,
    cooldown_seg: float = 15.0,
    hurst_actual: float = 0.42,
    irreversibilidad_lob: float = 0.0,
) -> Tuple[bool, str]:
    """
    Verifica el enfriamiento posterior a un bloqueo por Hurst alto en SHORT:
    Expande elasticamente la ventana (15.0s -> hasta 22.5s) cuando la entropia
    Markoviana del libro (irreversibilidad_lob) o el Hurst actual siguen elevados.
    """
    if ultimo_hurst_alto_ts <= 0.0:
        return True, "OK"
    irrev = float(irreversibilidad_lob or 0.0)
    h_act = float(hurst_actual or 0.42)
    extra_seg = (4.5 * max(0.0, irrev - 0.60)) + (12.0 * max(0.0, h_act - 0.485))
    cd_efectivo = min(22.5, max(float(cooldown_seg), float(cooldown_seg) + extra_seg))
    if (ahora_ts - ultimo_hurst_alto_ts) < cd_efectivo:
        return False, "SHORT_POST_HURST_COOLDOWN"
    return True, "OK"
