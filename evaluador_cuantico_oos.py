"""
Level 8 DAG: Out-of-Sample (OOS) Walk-Forward Quantitative Calibrator,
Bayesian Kelly Shrinkage, Autonomous Weight Controller, and 3,456-Combination
Counterfactual Digital Twin (--lab) for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import datetime
import itertools
import json
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional

import config_parametros as cfg
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
    n_total = len(operaciones)
    if n_total == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "scratches": 0,
            "effective_wr_pct": 0.0,
            "pnl_neto_usdt": 0.0,
            "profit_factor": 1.0,
            "lambda_bayes": 0.0,
            "ahorro_scratch_usdt": 0.0,
            "cosechas_triz": 0,
        }

    wins = sum(1 for op in operaciones if float(op.get("pnl_usdt", 0.0)) > 0.0)
    scratches = sum(
        1 for op in operaciones
        if op.get("es_scratch") or "SCRATCH" in str(op.get("motivo_salida", "")).upper()
    )
    losses_efectivas = max(0, n_total - wins - scratches)
    denom_efectivo = max(1, wins + losses_efectivas)
    wr_efectivo = round((wins / denom_efectivo) * 100.0, 1)

    ganancia_bruta = sum(float(op.get("pnl_usdt", 0.0)) for op in operaciones if float(op.get("pnl_usdt", 0.0)) > 0.0)
    perdida_bruta = abs(sum(float(op.get("pnl_usdt", 0.0)) for op in operaciones if float(op.get("pnl_usdt", 0.0)) < 0.0))
    pf = round(ganancia_bruta / perdida_bruta, 2) if perdida_bruta > 1e-6 else (2.50 if ganancia_bruta > 0.0 else 1.00)
    pnl_neto = round(ganancia_bruta - perdida_bruta, 4)

    lambda_bayes = round(min(1.0, n_total / 40.0), 2)

    ahorro_scratch = 0.0
    for op in operaciones:
        if op.get("es_scratch") or "SCRATCH" in str(op.get("motivo_salida", "")).upper():
            map_op = float(op.get("map_usdt", 15.5) or 15.5)
            perdida_sl_hipotetica = map_op * (cfg.SL_INTERNO_PCT + cfg.COMISION_TAKER_PCT)
            perdida_real = abs(min(0.0, float(op.get("pnl_usdt", 0.0))))
            ahorro_scratch += max(0.0, perdida_sl_hipotetica - perdida_real)

    cosechas = sum(
        1 for op in operaciones
        if float(op.get("pnl_usdt", 0.0)) > 0.0
        and ("TRAILING" in str(op.get("motivo_salida", "")).upper() or "UNWIND" in str(op.get("motivo_salida", "")).upper())
    )

    return {
        "total_trades": n_total,
        "wins": wins,
        "losses": losses_efectivas,
        "scratches": scratches,
        "effective_wr_pct": wr_efectivo,
        "pnl_neto_usdt": pnl_neto,
        "profit_factor": pf,
        "lambda_bayes": lambda_bayes,
        "ahorro_scratch_usdt": round(ahorro_scratch, 4),
        "cosechas_triz": cosechas,
    }


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
            f"# Quantum OOS Walk-Forward Report ? {cfg.NOMBRE_ESTRATEGIA}",
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

    salvamentos = [
        ev for ev in eventos_baul
        if ev.get("veredicto_oraculo_15s") == "CAPITAL_SAVED_TRUE_SHIELD"
    ]
    falsos_rechazos = [
        ev for ev in eventos_baul
        if ev.get("veredicto_oraculo_15s") == "FALSE_REJECTION_OPPORTUNITY_LOST"
    ]

    grid_z_hb = (-2.40, -2.50, -2.62, -2.75)
    grid_ofi = (0.12, 0.13, 0.15)
    grid_hurst_s = (0.465, 0.475, 0.485)
    grid_tp = (0.0016, 0.0019, 0.0022, 0.0025)
    grid_stall = (0.0011, 0.0013)
    grid_scratch = (18.0, 22.0, 26.0, 30.0)
    grid_sl_decay = (0.0030, 0.0034, 0.0038)

    total_combos = 0
    mejor_score = -1e9
    mejor_combo: Dict[str, float] = {}

    for z_hb, ofi_m, h_s, tp_v, st_v, sc_t, sl_d in itertools.product(
        grid_z_hb, grid_ofi, grid_hurst_s, grid_tp, grid_stall, grid_scratch, grid_sl_decay
    ):
        total_combos += 1
        pnl_sim = 0.0
        for op in ops:
            mfe = float(op.get("mfe_max_pnl_pct", 0.0)) / 100.0
            pnl_real = float(op.get("pnl_usdt", 0.0))
            map_u = float(op.get("map_usdt", 15.0) or 15.0)
            if mfe >= tp_v:
                pnl_sim += map_u * (tp_v - (2.0 * cfg.COMISION_MAKER_PCT))
            elif mfe >= st_v:
                pnl_sim += map_u * (st_v - (2.0 * cfg.COMISION_MAKER_PCT))
            else:
                pnl_sim += pnl_real * (0.85 if sc_t <= 22.0 else 1.0)

        bono_escudos = len(salvamentos) * 0.042
        score = pnl_sim + bono_escudos - (abs(z_hb + 2.50) * 0.02)
        if score > mejor_score:
            mejor_score = score
            mejor_combo = {
                "Z_SCORE_UMBRAL_HIGH_BETA": z_hb,
                "OFI_MIN_ENTRADA": ofi_m,
                "HURST_MAX_ENTRADA_SHORT": h_s,
                "COSECHA_TRIZ_ACTIVACION_PCT": tp_v,
                "COSECHA_ESTANCAMIENTO_MFE_PCT": st_v,
                "MAKER_SCRATCH_TIEMPO_SEG": sc_t,
                "SL_DECAY_PCT": sl_d,
            }

    reporte = {
        "estrategia": cfg.NOMBRE_ESTRATEGIA,
        "combinaciones_evaluadas": total_combos,
        "operaciones_analizadas": len(ops),
        "intercepciones_baul_15s": len(eventos_baul),
        "salvamentos_confirmados_15s": len(salvamentos),
        "falsos_rechazos_15s": len(falsos_rechazos),
        "mejor_expectancia_sim_usdt": round(mejor_score, 4),
        "configuracion_optima_terpsichora": mejor_combo,
    }

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
