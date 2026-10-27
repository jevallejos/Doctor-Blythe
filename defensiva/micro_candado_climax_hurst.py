# -*- coding: utf-8 -*-
"""
Micro-Modulo Defensivo #6: Candado Fisico Anti-Override de Hurst en SHORT-SNIPER
y Gobernador de Enfriamiento Post-Hurst (Prevencion del Caso WAL Trade #8 H=0.71).
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
) -> Tuple[bool, float, str]:
    """
    Evalua si un disparo SHORT-SNIPER cumple la barrera fractal de Hurst:
    - Regla base: H <= hurst_cap_base (0.485).
    - Si sens_climax_hurst_override esta activo y hay climax extremo (Z >= +5.20,
      OFI <= -0.80, Lyapunov <= -0.00050), permite un margen maximo hasta 0.515.
    - JAMAS permite vender en corto si H > 0.515 (evitando rupturas persistentes
      como H = 0.7089 en WAL Trade #8).
    Retorna (aprobado: bool, tope_aplicado: float, motivo: str).
    """
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    override_activo = float(ctrl.get("sens_climax_hurst_override", 1.0)) >= 0.5

    if hurst_actual <= hurst_cap_base:
        return True, hurst_cap_base, "OK"

    if hurst_actual > techo_duro_absoluto:
        return False, hurst_cap_base, f"H={hurst_actual:.3f}>{hurst_cap_base:.3f}"

    climax_agotado = (
        override_activo
        and z_score >= 5.20
        and ofi_actual <= -0.80
        and aceleracion_lyapunov <= -0.00050
    )
    if climax_agotado:
        return True, techo_duro_absoluto, "CLIMAX_HURST_CAPPED_OK"

    return False, hurst_cap_base, f"H={hurst_actual:.3f}>{hurst_cap_base:.3f}"


def verificar_enfriamiento_post_hurst_short(
    ahora_ts: float,
    ultimo_hurst_alto_ts: float,
    cooldown_seg: float = 15.0,
) -> Tuple[bool, str]:
    if ultimo_hurst_alto_ts > 0.0 and (ahora_ts - ultimo_hurst_alto_ts) < cooldown_seg:
        return False, "SHORT_POST_HURST_COOLDOWN"
    return True, "OK"
