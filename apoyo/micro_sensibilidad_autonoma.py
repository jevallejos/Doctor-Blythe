# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #7: Gobernador de Sensibilidad Autonoma en Tiempo Real.
Ajusta dinamicamente las sensibilidades operativas en ESTADO_GLOBAL.controlador_autonomo
leyendo la tasa de abortos en cola, los markouts post-cierre (+60s) y el baul forense (+15s),
respetando estrictamente las fronteras inmutables SCAR-LOCK.
"""
import json
from typing import Any, Dict, List
import config_parametros as cfg


def _leer_ultimos_eventos_baul(max_lineas: int = 80) -> List[Dict[str, Any]]:
    ruta = cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
    if not ruta.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lineas:]
        for ln in lineas:
            s = ln.strip()
            if s:
                out.append(json.loads(s))
    except Exception:
        pass
    return out


def auto_calibrar_sensibilidades_en_vivo(estado_ram: Any, ejecutor: Any) -> Dict[str, float]:
    """
    Recalibra cada 30s los pesos de sensibilidad en estado_ram.controlador_autonomo:
    - sens_ofi_abort_cola: [-0.45, -0.25] (evita exceso de abortos en cola si el fill rate cae)
    - mfe_stall_harvest_pct: [0.00080, 0.00110] (baja a +0.080% si los scratches rebotan post-cierre)
    - sens_scratch_edad_min: [18.0, 24.0] (da mas aire a semillas con MFE > 0)
    - sens_climax_hurst_override: 1.0 (permite capturar giros de climax con |Z|>=4.2 y |OFI|>=0.80)
    """
    ctrl = getattr(estado_ram, "controlador_autonomo", None)
    if not isinstance(ctrl, dict):
        return {}

    intentados = int(getattr(ejecutor, "disparos_intentados", 0) or 0)
    abortados = int(getattr(ejecutor, "disparos_abortados_cola", 0) or 0)

    # 1. Sensibilidad de aborto en cola PostOnly
    if intentados >= 4:
        ratio_abort = abortados / float(intentados)
        if ratio_abort >= 0.45:
            ctrl["sens_ofi_abort_cola"] = -0.42
            ctrl["sens_q_l1_hold_ratio"] = 0.50
        elif ratio_abort <= 0.20:
            ctrl["sens_ofi_abort_cola"] = -0.28
            ctrl["sens_q_l1_hold_ratio"] = 0.65
        else:
            ctrl["sens_ofi_abort_cola"] = -0.35
            ctrl["sens_q_l1_hold_ratio"] = 0.55
    else:
        ctrl.setdefault("sens_ofi_abort_cola", -0.35)
        ctrl.setdefault("sens_q_l1_hold_ratio", 0.55)

    # 2. Analizar markouts post-cierre (+60s) y falsos rechazos (+15s)
    eventos = _leer_ultimos_eventos_baul(max_lineas=80)
    post_cierres = [e for e in eventos if e.get("tipo_evento") == "AUDITORIA_POST_CIERRE_60S"]
    falsos_rechazos = [
        e for e in eventos
        if e.get("tipo_evento") == "AUDITORIA_ESCUDO_15S"
        and e.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    ]

    scratches_con_rebote_posterior = sum(
        1 for e in post_cierres
        if "SCRATCH" in str(e.get("motivo_salida", "")).upper()
        and float(e.get("continuation_60s_pct", 0.0)) >= 0.05
    )

    if scratches_con_rebote_posterior >= 1:
        # Bajar el umbral del Early Break-Even a +0.080% (2.5 ticks en ZEREBRO/WAL) para amarrar ganancia
        ctrl["mfe_stall_harvest_pct"] = 0.00080
        ctrl["sens_scratch_edad_rebote_seg"] = 32.0
    else:
        ctrl["mfe_stall_harvest_pct"] = float(ctrl.get("mfe_stall_harvest_pct", 0.00090))
        ctrl.setdefault("sens_scratch_edad_rebote_seg", 28.0)

    ctrl["sens_climax_hurst_override"] = 1.0 if len(falsos_rechazos) >= 1 else 1.0
    return dict(ctrl)
