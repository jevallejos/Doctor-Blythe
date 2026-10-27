"""
Level 8 DAG: Out-of-Sample (OOS) Walk-Forward Quantitative Calibrator,
Bayesian Kelly Shrinkage, Autonomous Weight Controller, and 3,456-Combination
Counterfactual Digital Twin (--lab) for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional

import config_parametros as cfg
from apoyo import micro_gemelo_digital_oos as mgd
import core_estado_ram as ram
import stats_tracker as st

_TZ_UTC = datetime.timezone.utc


def cargar_operaciones_ventana_72h(
    operaciones_mem: Optional[List[Dict[str, Any]]] = None,
    horas: float = 72.0,
) -> List[Dict[str, Any]]:
    fuente = (
        operaciones_mem
        if operaciones_mem is not None
        else st.GESTOR_ESTADISTICAS.operaciones
    )
    if not fuente:
        return []
    corte = time.time() - (horas * 3600.0)
    filtradas = [
        op for op in fuente
        if float(op.get("timestamp", time.time())) >= corte
    ]
    return filtradas if filtradas else list(fuente)


def cargar_eventos_baul_forense(ruta_baul: Optional[pathlib.Path] = None) -> List[Dict[str, Any]]:
    target = ruta_baul if ruta_baul is not None else cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
    if not target.exists():
        return []
    eventos: List[Dict[str, Any]] = []
    try:
        for ln in target.read_text(encoding="utf-8").splitlines():
            ln_s = ln.strip()
            if ln_s:
                eventos.append(json.loads(ln_s))
    except Exception:
        pass
    return eventos


def calcular_metricas_oos_72h(operaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    return mgd.calcular_metricas_oos_72h(operaciones)


def ejecutar_calibracion_walk_forward_oos(
    operaciones_mem: Optional[List[Dict[str, Any]]] = None,
    escribir_archivos: bool = True,
) -> Dict[str, Any]:
    ops_72h = cargar_operaciones_ventana_72h(operaciones_mem, horas=72.0)
    m72 = calcular_metricas_oos_72h(ops_72h)
    lam = m72["lambda_bayes"]
    pf = m72["profit_factor"]

    prior_kelly = 0.5500
    prior_z_hb = -2.5000
    prior_z_t1 = -2.1500
    prior_scratch = 18.0

    if pf >= 1.15:
        obs_kelly = 0.5800
        obs_z_hb = -2.4500
        obs_z_t1 = -2.1000
        obs_scratch = 20.0
    elif pf < 0.85 and m72["total_trades"] >= 1:
        obs_kelly = 0.3500
        obs_z_hb = -2.6200
        obs_z_t1 = -2.2500
        obs_scratch = 18.0
    else:
        obs_kelly = prior_kelly
        obs_z_hb = prior_z_hb
        obs_z_t1 = prior_z_t1
        obs_scratch = prior_scratch

    kelly_cal = round(((1.0 - lam) * prior_kelly) + (lam * obs_kelly), 4)
    z_hb_cal = round(((1.0 - lam) * prior_z_hb) + (lam * obs_z_hb), 4)
    z_t1_cal = round(((1.0 - lam) * prior_z_t1) + (lam * obs_z_t1), 4)
    scratch_cal = round(((1.0 - lam) * prior_scratch) + (lam * obs_scratch), 2)

    parametros_calibrados: Dict[str, float] = {
        "KELLY_FRACCION_BASE": kelly_cal,
        "Z_SCORE_UMBRAL_HIGH_BETA": z_hb_cal,
        "Z_SCORE_UMBRAL_TIER1": z_t1_cal,
        "OFI_MIN_ENTRADA": cfg.OFI_MIN_ENTRADA,
        "MAKER_SCRATCH_TIEMPO_SEG": scratch_cal,
        "COSECHA_TRIZ_ACTIVACION_PCT": cfg.COSECHA_TRIZ_ACTIVACION_PCT,
        "SL_INTERNO_PCT": cfg.SL_INTERNO_PCT,
        "TIEMPO_MAX_HOLD_SEG": cfg.TIEMPO_MAX_HOLD_SEG,
    }
    parametros_limpios = cfg.sanitizar_dict_calibracion_oos(parametros_calibrados)

    payload_oos: Dict[str, Any] = {
        "estrategia": cfg.NOMBRE_ESTRATEGIA,
        "codigo": cfg.CODIGO_ESTRATEGIA,
        "timestamp_utc": datetime.datetime.now(_TZ_UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "metricas_72h": m72,
        "parametros_calibrados": parametros_limpios,
        "controlador_autonomo": dict(ram.ESTADO_GLOBAL.controlador_autonomo),
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
        ruta_json.write_bytes(texto_json.encode("utf-8"))

        ruta_md = cfg.obtener_ruta_archivo("ARCHIVO_REPORTE_OOS_MD")
        md_lines = [
            f"# Quantum OOS Walk-Forward Report - {cfg.NOMBRE_ESTRATEGIA}",
            "",
            f"* **Timestamp:** `{payload_oos['timestamp_utc']}`",
            f"* **Sample (72h):** `{m72['total_trades']} trades`",
            f"* **Effective Win Rate:** `{m72['effective_wr_pct']:.1f}%`",
            f"* **Net PnL (72h):** `{m72['pnl_neto_usdt']:+.4f} USDT`",
            f"* **Profit Factor:** `{m72['profit_factor']:.2f}`",
            f"* **Scratch Capital Saved:** `+{m72['ahorro_scratch_usdt']:.4f} USDT`",
            "",
        ]
        ruta_md.write_bytes(("\n".join(md_lines) + "\n").encode("utf-8"))

    return payload_oos


def ejecutar_laboratorio_gemelo_digital_3456(escribir_disco: bool = True) -> Dict[str, Any]:
    ops = cargar_operaciones_ventana_72h(horas=168.0)
    eventos_baul = cargar_eventos_baul_forense()
    reporte = mgd.simular_malla_gemelo_3456(ops, eventos_baul)
    if escribir_disco and not cfg.es_modo_test():
        ruta_lab = cfg.obtener_ruta_archivo("ARCHIVO_REPORTE_LAB_JSON")
        ruta_lab.write_bytes(
            (json.dumps(reporte, indent=2, ensure_ascii=True).replace("\r\n", "\n") + "\n").encode("utf-8")
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
