# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #6: Inspector Forense Anatomico (verbot -a).
Analiza tribrain_stats_v1.jsonl y baul_ia_forense.jsonl para mostrar en consola:
1. Desempeno detallado por Par Campeon (WR, PnL, MFE, MAE, LVR).
2. Efectividad de cada Escudo en defensiva/ (+15s Counterfactual Vault).
3. Markout Post-Cierre (+15s / +30s / +60s): Ahorro real de Maker-Scratch y Captura de Wald.
"""
import collections
import json
from typing import Any, Dict, List
import config_parametros as cfg
import stats_tracker as st

_C_RESET = "\033[0m"
_C_CYAN = "\033[1;96m"
_C_GREEN = "\033[1;92m"
_C_RED = "\033[1;91m"
_C_YELLOW = "\033[1;93m"
_C_WHITE = "\033[1;97m"


def _cargar_baul() -> List[Dict[str, Any]]:
    ruta = cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
    if not ruta.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for ln in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
            s = ln.strip()
            if s:
                out.append(json.loads(s))
    except Exception:
        pass
    return out


def generar_reporte_anatomico_dict() -> Dict[str, Any]:
    st.GESTOR_ESTADISTICAS.cargar_historial_disco()
    ops = list(st.GESTOR_ESTADISTICAS.operaciones)
    eventos = _cargar_baul()

    por_par: Dict[str, Dict[str, Any]] = {}
    for par in cfg.PARES_CAMPEONES:
        por_par[par] = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "scratches": 0,
            "pnl_usdt": 0.0,
            "mfe_sum": 0.0,
            "mae_sum": 0.0,
        }

    for op in ops:
        sym = str(op.get("symbol", ""))
        if sym not in por_par:
            por_par[sym] = {
                "trades": 0, "wins": 0, "losses": 0, "scratches": 0,
                "pnl_usdt": 0.0, "mfe_sum": 0.0, "mae_sum": 0.0,
            }
        d = por_par[sym]
        d["trades"] += 1
        pnl = float(op.get("pnl_usdt", 0.0))
        es_sc = bool(op.get("es_scratch")) or ("SCRATCH" in str(op.get("motivo_salida", "")).upper())
        if pnl > 0.0:
            d["wins"] += 1
        elif es_sc:
            d["scratches"] += 1
        else:
            d["losses"] += 1
        d["pnl_usdt"] = round(d["pnl_usdt"] + pnl, 4)
        d["mfe_sum"] += float(op.get("mfe_max_pnl_pct", 0.0))
        d["mae_sum"] += float(op.get("mae_min_pnl_pct", 0.0))

    escudos_stats: Dict[str, Dict[str, Any]] = collections.defaultdict(
        lambda: {"total": 0, "saved": 0, "false_rej": 0, "chop": 0, "usdt_saved": 0.0}
    )
    post_exit_events: List[Dict[str, Any]] = []

    for ev in eventos:
        t_ev = str(ev.get("tipo_evento", ""))
        if t_ev == "AUDITORIA_ESCUDO_15S":
            esc = str(ev.get("escudo", "UNKNOWN"))
            ver = str(ev.get("veredicto_oraculo_15s", ""))
            st_e = escudos_stats[esc]
            st_e["total"] += 1
            if ver == "CAPITAL_SAVED_TRUE_SHIELD":
                st_e["saved"] += 1
            elif ver == "FALSE_REJECTION_OPPORTUNITY_LOST":
                st_e["false_rej"] += 1
            else:
                st_e["chop"] += 1
            st_e["usdt_saved"] = round(st_e["usdt_saved"] + float(ev.get("ahorro_estimado_usdt", 0.0)), 4)
        elif t_ev == "AUDITORIA_POST_CIERRE_60S":
            post_exit_events.append(ev)

    return {
        "resumen_global": st.GESTOR_ESTADISTICAS.obtener_resumen(),
        "por_par": por_par,
        "escudos_15s": dict(escudos_stats),
        "post_cierre_60s": post_exit_events,
    }


def imprimir_auditoria_forense_cli() -> None:
    rep = generar_reporte_anatomico_dict()
    res = rep["resumen_global"]
    print(f"{_C_CYAN}{'=' * 86}{_C_RESET}")
    print(f"{_C_WHITE} [FORENSIC ANATOMY INSPECTOR - verbot -a] {cfg.NOMBRE_ESTRATEGIA}{_C_RESET}")
    print(f"{_C_CYAN}{'=' * 86}{_C_RESET}")
    c_pnl = _C_GREEN if res["total_pnl_usdt"] >= 0.0 else _C_RED
    print(
        f" Global Trades: {res['trades']} (W:{res['wins']} / L:{res['losses']} / S:{res['scratches']}) | "
        f"WR: {res['win_rate']:.1f}% | Net PnL: {c_pnl}{res['total_pnl_usdt']:+.4f} USDT{_C_RESET} | "
        f"UTA Balance: {_C_WHITE}{res['real_usdt']:.4f} USDT{_C_RESET}"
    )
    print(f"{_C_CYAN}{'-' * 86}{_C_RESET}")
    print(f"{_C_WHITE} 1. BREAKDOWN BY CHAMPION PAIR (OFFENSIVE & SIZING EFFICIENCY){_C_RESET}")
    print(f" {'PAIR':<20} | {'TRADES':<6} | {'W / L / S':<11} | {'EFF WR':<7} | {'AVG MFE':<8} | {'NET PNL (USDT)':<14}")
    print(f" {'-' * 82}")
    for par, d in rep["por_par"].items():
        tr = d["trades"]
        w, l, s = d["wins"], d["losses"], d["scratches"]
        eff_den = max(1, w + max(0, l))
        eff_wr = (w / eff_den) * 100.0 if (w + l) > 0 else 0.0
        avg_mfe = (d["mfe_sum"] / tr) if tr > 0 else 0.0
        col = _C_GREEN if d["pnl_usdt"] > 0.0 else (_C_RED if d["pnl_usdt"] < 0.0 else _C_WHITE)
        wls_str = f"{w}W/{l}L/{s}S"
        print(
            f" {par:<20} | {tr:<6d} | {wls_str:<11} | {eff_wr:5.1f}%  | "
            f"{avg_mfe:+6.3f}% | {col}{d['pnl_usdt']:+10.4f} USDT{_C_RESET}"
        )

    print(f"{_C_CYAN}{'-' * 86}{_C_RESET}")
    print(f"{_C_WHITE} 2. DEFENSIVE SHIELD ACCURACY (+15.0s COUNTERFACTUAL ORACLE){_C_RESET}")
    esc_map = rep["escudos_15s"]
    if not esc_map:
        print(f" {_C_YELLOW}[INFO] No +15s shield interceptions recorded in current epoch yet.{_C_RESET}")
    else:
        print(f" {'SHIELD NAME':<22} | {'BLOCKS':<6} | {'SAVED':<6} | {'CHOP':<6} | {'FALSE_REJ':<9} | {'EST. SAVED'}")
        print(f" {'-' * 82}")
        for esc, st_e in sorted(esc_map.items(), key=lambda x: x[1]["total"], reverse=True):
            print(
                f" {esc:<22} | {st_e['total']:<6d} | {_C_GREEN}{st_e['saved']:<6d}{_C_RESET} | "
                f"{st_e['chop']:<6d} | {_C_YELLOW}{st_e['false_rej']:<9d}{_C_RESET} | "
                f"{_C_GREEN}+{st_e['usdt_saved']:.4f} USDT{_C_RESET}"
            )

    print(f"{_C_CYAN}{'-' * 86}{_C_RESET}")
    print(f"{_C_WHITE} 3. POST-EXIT MARKOUT TRACKER (+15s / +30s / +60s AFTER CLOSE){_C_RESET}")
    post_list = rep["post_cierre_60s"]
    if not post_list:
        print(f" {_C_YELLOW}[INFO] Post-exit markout tracker active (waiting for closed trades +60s).{_C_RESET}")
    else:
        ahorro_sc = sum(float(x.get("ahorro_post_scratch_usdt", 0.0)) for x in post_list)
        ultimos_p = post_list[-5:]
        print(f" Total Confirmed Post-Scratch Capital Saved (+60s): {_C_GREEN}+{ahorro_sc:.4f} USDT{_C_RESET}")
        for ev_p in ultimos_p:
            print(
                f"   -> Trade #{ev_p.get('trade_id')} {ev_p.get('symbol')} [{ev_p.get('motivo_salida')}] "
                f"PnL={ev_p.get('pnl_usdt', 0.0):+.4f} USDT | "
                f"Post-Exit +15s:{ev_p.get('continuation_15s_pct', 0.0):+.3f}% "
                f"+30s:{ev_p.get('continuation_30s_pct', 0.0):+.3f}% "
                f"+60s:{ev_p.get('continuation_60s_pct', 0.0):+.3f}% ({ev_p.get('veredicto_post_cierre', '')})"
            )
    print(f"{_C_CYAN}{'=' * 86}{_C_RESET}")
