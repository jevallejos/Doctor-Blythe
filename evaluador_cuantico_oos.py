# File: evaluador_cuantico_oos.py
"""
Level 8 DAG: Out-of-Sample (OOS) Walk-Forward Quantitative Calibrator, Continuous
Empirical-Bayes Shrinkage with CVaR_10% & MFE-Capture Feedback, Autonomous Weight
Controller Synchronization, Atomic Tempfile-Fsync-Replace Persistence, and
3,456-Combination Counterfactual Digital Twin (--lab) for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import pathlib
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

import config_parametros as cfg
from apoyo import micro_gemelo_digital_oos as mgd
from apoyo import micro_inspector_forense as mif
from apoyo import micro_sensibilidad_autonoma as msa
import core_estado_ram as ram
import stats_tracker as st

_TZ_UTC = datetime.timezone.utc


def _escribir_bytes_atomico(ruta_destino: pathlib.Path, data: bytes) -> None:
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(
        prefix=f".tmp_{ruta_destino.name}_",
        dir=str(ruta_destino.parent),
    )
    tmp_path = pathlib.Path(tmp_str)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(ruta_destino))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def cargar_eventos_baul_forense(ruta_baul: Optional[pathlib.Path] = None) -> List[Dict[str, Any]]:
    if ruta_baul is None:
        return mif.cargar_eventos_baul_forense()
    if not ruta_baul.exists():
        return []
    return [json.loads(ln.strip()) for ln in ruta_baul.read_text(encoding="utf-8").splitlines() if ln.strip()]


def cargar_operaciones_ventana_72h(
    operaciones_mem: Optional[List[Dict[str, Any]]] = None,
    horas: float = 72.0,
) -> List[Dict[str, Any]]:
    if operaciones_mem is not None:
        fuente = list(operaciones_mem)
    else:
        if not cfg.es_modo_test():
            st.GESTOR_ESTADISTICAS.cargar_historial_disco()
        fuente = list(st.GESTOR_ESTADISTICAS.operaciones)
        if not fuente and not cfg.es_modo_test():
            eventos_b = cargar_eventos_baul_forense()
            fuente = [e for e in eventos_b if e.get("tipo_evento") == "CIERRE_OPERACION_REAL"]
    if not fuente:
        return []
    corte = time.time() - (horas * 3600.0)
    filtradas = [
        op for op in fuente
        if float(op.get("timestamp", time.time())) >= corte
    ]
    return filtradas if filtradas else list(fuente)


def calcular_cvar_10pct_adversarial(retornos_usdt: List[float]) -> float:
    return mgd.calcular_cvar_10pct_adversarial(retornos_usdt)


def calcular_metricas_oos_72h(operaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    return mgd.calcular_metricas_oos_72h(operaciones)


def ejecutar_calibracion_walk_forward_oos(
    operaciones_mem: Optional[List[Dict[str, Any]]] = None,
    escribir_archivos: bool = True,
) -> Dict[str, Any]:
    ops_72h = cargar_operaciones_ventana_72h(operaciones_mem, horas=72.0)
    m72 = calcular_metricas_oos_72h(ops_72h)
    lam = float(m72["lambda_bayes"])
    pf = float(m72["profit_factor"])
    n_tr = int(m72["total_trades"])
    cvar_10 = float(m72.get("cvar_10pct_usdt", 0.0) or 0.0)
    avg_cap = float(m72.get("avg_mfe_capture_ratio", 0.65) or 0.65)
    tk_ratio = float(m72.get("taker_exit_ratio", 0.0) or 0.0)

    prior_kelly = 0.5500
    prior_z_hb = -2.5000
    prior_z_t1 = -2.1500
    prior_scratch = 18.0
    prior_tp = float(cfg.COSECHA_TRIZ_ACTIVACION_PCT)

    if pf >= 1.15:
        bono_pf = math.tanh((pf - 1.15) / 0.80)
        obs_kelly = min(0.6000, 0.5800 + (0.0200 * bono_pf))
        obs_z_hb = -2.4500
        obs_z_t1 = -2.1000
        obs_scratch = 20.0
        obs_tp = min(0.0018, prior_tp + (0.00015 if avg_cap >= 0.70 else 0.0))
    elif pf < 0.85 and n_tr >= 1:
        penal_cola = 0.0200 if (cvar_10 <= -0.045 or tk_ratio >= 0.35) else 0.0
        obs_kelly = max(0.3200, 0.3500 - penal_cola)
        obs_z_hb = -2.6200 - (0.0400 if tk_ratio >= 0.35 else 0.0)
        obs_z_t1 = -2.2500 - (0.0300 if tk_ratio >= 0.35 else 0.0)
        obs_scratch = 24.0 if (n_tr >= 6 and m72["scratches"] > m72["losses"]) else 18.0
        obs_tp = max(0.0013, prior_tp - (0.00010 if avg_cap < 0.35 else 0.0))
    else:
        obs_kelly = prior_kelly
        obs_z_hb = prior_z_hb
        obs_z_t1 = prior_z_t1
        obs_scratch = prior_scratch
        obs_tp = prior_tp

    kelly_cal = round(((1.0 - lam) * prior_kelly) + (lam * obs_kelly), 4)
    z_hb_cal = round(((1.0 - lam) * prior_z_hb) + (lam * obs_z_hb), 4)
    z_t1_cal = round(((1.0 - lam) * prior_z_t1) + (lam * obs_z_t1), 4)
    scratch_cal = round(((1.0 - lam) * prior_scratch) + (lam * obs_scratch), 2)
    tp_cal = round(((1.0 - lam) * prior_tp) + (lam * obs_tp), 5)

    if not cfg.es_modo_test():
        try:
            msa.auto_calibrar_sensibilidades_en_vivo(ram.ESTADO_GLOBAL, None)
        except Exception:
            pass

    ctrl_vivo = dict(ram.ESTADO_GLOBAL.controlador_autonomo)
    if hasattr(cfg, "sanitizar_controlador_autonomo"):
        ctrl_vivo = cfg.sanitizar_controlador_autonomo(ctrl_vivo)

    ofi_cal = float(ctrl_vivo.get("w1_ofi_long", cfg.OFI_MIN_ENTRADA))
    parametros_calibrados: Dict[str, float] = {
        "KELLY_FRACCION_BASE": kelly_cal,
        "Z_SCORE_UMBRAL_HIGH_BETA": z_hb_cal,
        "Z_SCORE_UMBRAL_TIER1": z_t1_cal,
        "OFI_MIN_ENTRADA": ofi_cal,
        "MAKER_SCRATCH_TIEMPO_SEG": scratch_cal,
        "COSECHA_TRIZ_ACTIVACION_PCT": tp_cal,
        "SL_INTERNO_PCT": cfg.SL_INTERNO_PCT,
        "TIEMPO_MAX_HOLD_SEG": cfg.TIEMPO_MAX_HOLD_SEG,
    }
    parametros_limpios = cfg.sanitizar_dict_calibracion_oos(parametros_calibrados)

    ctrl_export = {
        **ctrl_vivo,
        "w1_ofi_long": float(parametros_limpios.get("OFI_MIN_ENTRADA", cfg.OFI_MIN_ENTRADA)),
        "w3_tp_maker_pct": float(
            ctrl_vivo.get(
                "w3_tp_maker_pct",
                parametros_limpios.get("COSECHA_TRIZ_ACTIVACION_PCT", cfg.COSECHA_TRIZ_ACTIVACION_PCT),
            )
        ),
    }

    payload_oos: Dict[str, Any] = {
        "estrategia": cfg.NOMBRE_ESTRATEGIA,
        "codigo": cfg.CODIGO_ESTRATEGIA,
        "timestamp_utc": datetime.datetime.now(_TZ_UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "metricas_72h": m72,
        "parametros_calibrados": parametros_limpios,
        "controlador_autonomo": ctrl_export,
    }

    ram.log_operativo("=" * 66)
    ram.log_operativo(f"[QUANTUM OOS EVALUATOR] {cfg.NOMBRE_ESTRATEGIA}")
    ram.log_operativo("=" * 66)
    ram.log_operativo(
        f"   -> Base Sample (72h)  : {m72['total_trades']} trades | "
        f"Effective WR: {m72['effective_wr_pct']:.1f}% | "
        f"PnL: {m72['pnl_neto_usdt']:+.4f} USDT | PF: {m72['profit_factor']:.2f} | "
        f"Lambda Bayes: {m72['lambda_bayes']:.2f}"
    )
    ram.log_operativo(
        f"   -> Maker Scratch Saved: +{m72['ahorro_scratch_usdt']:.4f} USDT saved from hitting Stop-Loss | "
        f"TRIZ Harvests: {m72['cosechas_triz']}"
    )
    ram.log_operativo(
        f"   -> Hot-Reload JSON    : Kelly={parametros_limpios['KELLY_FRACCION_BASE'] * 100:.1f}% | "
        f"Z_HB={parametros_limpios['Z_SCORE_UMBRAL_HIGH_BETA']:.4f} | "
        f"Scratch={parametros_limpios['MAKER_SCRATCH_TIEMPO_SEG']:.2f}s | "
        f"SL=-{parametros_limpios['SL_INTERNO_PCT'] * 100:.2f}%"
    )

    if escribir_archivos:
        ruta_json = cfg.obtener_ruta_archivo("ARCHIVO_CALIBRACION_OOS")
        texto_json = json.dumps(payload_oos, indent=2, ensure_ascii=True).replace("\r\n", "\n") + "\n"
        _escribir_bytes_atomico(ruta_json, texto_json.encode("utf-8"))

        ruta_md = cfg.obtener_ruta_archivo("ARCHIVO_REPORTE_OOS_MD")
        md_lines = [
            f"# Quantum OOS Walk-Forward Report - {cfg.NOMBRE_ESTRATEGIA}",
            "",
            f"* **Timestamp:** `{payload_oos['timestamp_utc']}`",
            f"* **Sample (72h):** `{m72['total_trades']} trades`",
            f"* **Effective Win Rate:** `{m72['effective_wr_pct']:.1f}%`",
            f"* **Net PnL (72h):** `{m72['pnl_neto_usdt']:+.4f} USDT`",
            f"* **Profit Factor:** `{m72['profit_factor']:.2f}`",
            f"* **CVaR 10% (Adversarial):** `{cvar_10:+.4f} USDT`",
            f"* **Avg MFE Capture Ratio:** `{avg_cap:+.4f}`",
            f"* **Taker Exit Ratio:** `{tk_ratio * 100:.1f}%`",
            f"* **Scratch Capital Saved:** `+{m72['ahorro_scratch_usdt']:.4f} USDT`",
            "",
        ]
        _escribir_bytes_atomico(ruta_md, ("\n".join(md_lines) + "\n").encode("utf-8"))

    return payload_oos


def ejecutar_laboratorio_gemelo_digital_3456(escribir_disco: bool = True) -> Dict[str, Any]:
    ops = cargar_operaciones_ventana_72h(horas=168.0)
    eventos_baul = cargar_eventos_baul_forense()
    reporte = mgd.simular_malla_gemelo_3456(ops, eventos_baul)
    if escribir_disco and not cfg.es_modo_test():
        ruta_lab = cfg.obtener_ruta_archivo("ARCHIVO_REPORTE_LAB_JSON")
        _escribir_bytes_atomico(
            ruta_lab,
            (json.dumps(reporte, indent=2, ensure_ascii=True).replace("\r\n", "\n") + "\n").encode("utf-8"),
        )
    return reporte


def main() -> int:
    if "--lab" in sys.argv:
        rep = ejecutar_laboratorio_gemelo_digital_3456(escribir_disco=True)
        print(json.dumps(rep, indent=2))
        return 0
    ejecutar_calibracion_walk_forward_oos(escribir_archivos=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
