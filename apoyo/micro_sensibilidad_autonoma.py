# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #7: Gobernador de Sensibilidad Autonoma en Tiempo Real con
Aprendizaje por Retroalimentacion No Censurada de Ordenes PostOnly Expiradas
(OPSR, arXiv:2605.19584 COLT 2026).
"""
from typing import Any, Dict
import config_parametros as cfg
from apoyo import micro_inspector_forense as mif


def auto_calibrar_sensibilidades_en_vivo(estado_ram: Any, ejecutor: Any) -> Dict[str, float]:
    """
    Recalibra cada 30s los pesos de sensibilidad en estado_ram.controlador_autonomo:
    - Evalua tanto la tasa de abortos en cola como la retroalimentacion contrafactual
      no censurada (+15.0s OPSR) de ordenes PostOnly expiradas o abortadas en cola.
    """
    ctrl = getattr(estado_ram, "controlador_autonomo", None)
    if not isinstance(ctrl, dict):
        return {}

    intentados = int(getattr(ejecutor, "disparos_intentados", 0) or 0)
    abortados = int(getattr(ejecutor, "disparos_abortados_cola", 0) or 0)

    if intentados >= 4:
        ratio_abort = abortados / float(intentados)
        if ratio_abort >= 0.45:
            ctrl["sens_ofi_abort_cola"] = -0.42
            ctrl["sens_q_l1_hold_ratio"] = 0.50
        elif ratio_abort <= 0.20:
            ctrl["sens_ofi_abort_cola"] = -0.28
            ctrl["sens_q_l1_hold_ratio"] = 0.65
        else:
            ctrl["sens_ofi_abort_cola"] = -0.48
            ctrl["sens_q_l1_hold_ratio"] = 0.22
    else:
        ctrl["sens_ofi_abort_cola"] = -0.48
        ctrl["sens_q_l1_hold_ratio"] = 0.22

    eventos = mif.cargar_eventos_baul_forense(max_lineas=80)
    post_cierres = [e for e in eventos if e.get("tipo_evento") == "AUDITORIA_POST_CIERRE_60S"]
    falsos_rechazos = [
        e for e in eventos
        if e.get("tipo_evento") == "AUDITORIA_ESCUDO_15S"
        and e.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    ]

    # Mejora #5 (OPSR COLT 2026 - arXiv:2605.19584): Retroalimentacion no censurada de cola L1
    opsr_eventos = [
        e for e in eventos
        if e.get("tipo_evento") == "AUDITORIA_ESCUDO_15S"
        and str(e.get("escudo", "")).startswith("OPSR_")
    ]
    opsr_missed_alpha = sum(
        1 for e in opsr_eventos if e.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    )
    opsr_true_saves = sum(
        1 for e in opsr_eventos if e.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    )
    if opsr_missed_alpha >= (opsr_true_saves + 2):
        ctrl["sens_q_l1_hold_ratio"] = max(0.18, round(float(ctrl["sens_q_l1_hold_ratio"]) - 0.05, 2))
        ctrl["sens_ofi_abort_cola"] = max(-0.44, round(float(ctrl["sens_ofi_abort_cola"]) - 0.04, 2))
    elif opsr_true_saves >= (opsr_missed_alpha + 2):
        ctrl["sens_q_l1_hold_ratio"] = min(0.68, round(float(ctrl["sens_q_l1_hold_ratio"]) + 0.05, 2))
        ctrl["sens_ofi_abort_cola"] = min(-0.26, round(float(ctrl["sens_ofi_abort_cola"]) + 0.04, 2))

    scratches_con_rebote_posterior = sum(
        1 for e in post_cierres[-6:]
        if "SCRATCH" in str(e.get("motivo_salida", "")).upper()
        and float(e.get("continuation_60s_pct", 0.0)) >= 0.05
    )
    if scratches_con_rebote_posterior >= 1:
        ctrl["mfe_stall_harvest_pct"] = 0.00080
        ctrl["sens_scratch_edad_rebote_seg"] = 32.0
    else:
        ctrl["mfe_stall_harvest_pct"] = float(cfg.COSECHA_ESTANCAMIENTO_MFE_PCT)
        ctrl["sens_scratch_edad_rebote_seg"] = 28.0

    ctrl["sens_climax_hurst_override"] = 0.0 if (opsr_true_saves >= (opsr_missed_alpha + 3) and len(falsos_rechazos) == 0) else 1.0
    return dict(ctrl)
