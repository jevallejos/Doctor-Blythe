# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #6: Inspector Forense Anatomico de 5 Niveles (verbot -a)
con Atribucion de los 8 Atributos de Orden Superior, Deduplicacion Markoviana
de Escudos (+15s) y Memoria Bayesiana Completa de los 6 Pares Campeones para
HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import collections
import json
from typing import Any, Dict, List

import config_parametros as cfg
import core_estado_ram as ram
import stats_tracker as st

_C_RESET = "\033[0m"
_C_CYAN = "\033[1;96m"
_C_GREEN = "\033[1;92m"
_C_RED = "\033[1;91m"
_C_YELLOW = "\033[1;93m"
_C_MAGENTA = "\033[1;95m"
_C_WHITE = "\033[1;97m"


def cargar_eventos_baul_forense(max_lineas: int = 0) -> List[Dict[str, Any]]:
    ruta = cfg.obtener_ruta_archivo("ARCHIVO_BAUL_IA_JSONL")
    if not ruta.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        if max_lineas > 0:
            lineas = lineas[-max_lineas:]
        for ln in lineas:
            s = ln.strip()
            if s:
                out.append(json.loads(s))
    except Exception:
        pass
    return out


def generar_reporte_anatomico_dict() -> Dict[str, Any]:
    st.GESTOR_ESTADISTICAS.cargar_historial_disco()
    ops = list(st.GESTOR_ESTADISTICAS.operaciones)
    eventos = cargar_eventos_baul_forense()
    if not ops and not cfg.es_modo_test():
        ops = [e for e in eventos if e.get("tipo_evento") == "CIERRE_OPERACION_REAL"]

    por_par: Dict[str, Dict[str, Any]] = {}
    for par in cfg.PARES_CAMPEONES:
        por_par[par] = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "scratches": 0,
            "pnl_usdt": 0.0,
            "fees_usdt": 0.0,
            "mfe_sum": 0.0,
            "mae_sum": 0.0,
            "lvr_sum": 0.0,
            "cap_sum": 0.0,
            "repeg_sum": 0.0,
        }

    por_motivo: Dict[str, Dict[str, Any]] = collections.defaultdict(
        lambda: {
            "trades": 0,
            "maker_exits": 0,
            "gross_usdt": 0.0,
            "fees_usdt": 0.0,
            "net_usdt": 0.0,
            "mfe_sum": 0.0,
            "gross_pct_sum": 0.0,
            "hold_sum": 0.0,
            "cap_sum": 0.0,
            "repeg_sum": 0.0,
            "wald_sum": 0.0,
            "vacio_sum": 0.0,
        }
    )

    maker_exit_stats = {"trades": 0, "gross": 0.0, "fees": 0.0, "net": 0.0}
    taker_exit_stats = {"trades": 0, "gross": 0.0, "fees": 0.0, "net": 0.0}

    for op in ops:
        sym = str(op.get("symbol", ""))
        if sym not in por_par:
            por_par[sym] = {
                "trades": 0, "wins": 0, "losses": 0, "scratches": 0,
                "pnl_usdt": 0.0, "fees_usdt": 0.0, "mfe_sum": 0.0, "mae_sum": 0.0,
                "lvr_sum": 0.0, "cap_sum": 0.0, "repeg_sum": 0.0,
            }
        d = por_par[sym]
        d["trades"] += 1
        pnl = float(op.get("pnl_usdt", 0.0))
        fee = float(op.get("fees_usdt", 0.0))
        gross = pnl + fee
        mfe_v = float(op.get("mfe_max_pnl_pct", 0.0))
        mae_v = abs(float(op.get("mae_min_pnl_pct", 0.0)))
        lvr_v = float(op.get("lvr_bps", 0.0))
        hold_v = float(op.get("hold_seg", 0.0))
        map_v = max(1e-6, float(op.get("map_usdt", 14.0) or 14.0))
        gross_pct = (gross / map_v) * 100.0
        motivo = str(op.get("motivo_salida", "UNKNOWN"))
        es_sc = bool(op.get("es_scratch")) or ("SCRATCH" in motivo.upper())
        es_out_maker = bool(op.get("es_salida_maker", True))

        vec_in = op.get("vector_entrada") if isinstance(op.get("vector_entrada"), dict) else {}
        cap_v = max(-1.50, min(1.50, float(vec_in.get("mfe_capture_ratio", 0.0) or 0.0)))
        rep_v = float(vec_in.get("repeg_salida_count", 0.0) or 0.0)
        wald_v = float(vec_in.get("lambda_wald_exit", 0.0) or 0.0)
        vac_v = float(vec_in.get("vacio_l2_ratio", 1.0) or 1.0)

        if pnl > 0.0:
            d["wins"] += 1
        elif es_sc:
            d["scratches"] += 1
        else:
            d["losses"] += 1

        d["pnl_usdt"] = round(d["pnl_usdt"] + pnl, 4)
        d["fees_usdt"] = round(d["fees_usdt"] + fee, 4)
        d["mfe_sum"] += mfe_v
        d["mae_sum"] += mae_v
        d["lvr_sum"] += lvr_v
        d["cap_sum"] += cap_v
        d["repeg_sum"] += rep_v

        dm = por_motivo[motivo]
        dm["trades"] += 1
        if es_out_maker:
            dm["maker_exits"] += 1
        dm["gross_usdt"] = round(dm["gross_usdt"] + gross, 4)
        dm["fees_usdt"] = round(dm["fees_usdt"] + fee, 4)
        dm["net_usdt"] = round(dm["net_usdt"] + pnl, 4)
        dm["mfe_sum"] += mfe_v
        dm["gross_pct_sum"] += gross_pct
        dm["hold_sum"] += hold_v
        dm["cap_sum"] += cap_v
        dm["repeg_sum"] += rep_v
        dm["wald_sum"] += wald_v
        dm["vacio_sum"] += vac_v

        bucket_rol = maker_exit_stats if es_out_maker else taker_exit_stats
        bucket_rol["trades"] += 1
        bucket_rol["gross"] = round(bucket_rol["gross"] + gross, 4)
        bucket_rol["fees"] = round(bucket_rol["fees"] + fee, 4)
        bucket_rol["net"] = round(bucket_rol["net"] + pnl, 4)

    escudos_stats: Dict[str, Dict[str, Any]] = collections.defaultdict(
        lambda: {"total": 0, "episodios": 0, "saved": 0, "false_rej": 0, "chop": 0, "usdt_saved": 0.0}
    )
    post_exit_events: List[Dict[str, Any]] = []
    ultimo_ts_esc: Dict[str, float] = {}

    for ev in eventos:
        t_ev = str(ev.get("tipo_evento", ""))
        if t_ev == "AUDITORIA_ESCUDO_15S":
            esc = str(ev.get("escudo", "UNKNOWN"))
            sym_e = str(ev.get("symbol", ""))
            dir_e = str(ev.get("direccion", ""))
            ts_e = float(ev.get("timestamp", 0.0) or 0.0)
            ver = str(ev.get("veredicto_oraculo_15s", ""))
            st_e = escudos_stats[esc]
            st_e["total"] += 1

            clave_ep = f"{sym_e}|{esc}|{dir_e}"
            es_nuevo_ep = (ts_e - ultimo_ts_esc.get(clave_ep, -1e9)) >= 15.0
            if es_nuevo_ep:
                ultimo_ts_esc[clave_ep] = ts_e
                st_e["episodios"] += 1

            if ver == "CAPITAL_SAVED_TRUE_SHIELD":
                st_e["saved"] += 1
                if es_nuevo_ep:
                    st_e["usdt_saved"] = round(
                        st_e["usdt_saved"] + float(ev.get("ahorro_estimado_usdt", 0.0)), 4
                    )
            elif ver == "FALSE_REJECTION_OPPORTUNITY_LOST":
                st_e["false_rej"] += 1
            else:
                st_e["chop"] += 1
        elif t_ev == "AUDITORIA_POST_CIERRE_60S":
            post_exit_events.append(ev)

    res_glob = dict(st.GESTOR_ESTADISTICAS.obtener_resumen())
    tot_tr = sum(d["trades"] for d in por_par.values())
    if tot_tr > int(res_glob.get("trades", 0)):
        tot_w = sum(d["wins"] for d in por_par.values())
        tot_l = sum(d["losses"] for d in por_par.values())
        tot_s = sum(d["scratches"] for d in por_par.values())
        tot_pnl = round(sum(d["pnl_usdt"] for d in por_par.values()), 4)
        eff_den_g = max(1, tot_w + tot_l)
        res_glob["trades"] = tot_tr
        res_glob["wins"] = tot_w
        res_glob["losses"] = tot_l
        res_glob["scratches"] = tot_s
        res_glob["win_rate"] = round((tot_w / eff_den_g) * 100.0, 1) if (tot_w + tot_l) > 0 else 0.0
        res_glob["total_pnl_usdt"] = tot_pnl

    return {
        "resumen_global": res_glob,
        "por_par": por_par,
        "por_motivo": dict(por_motivo),
        "rol_salida": {"maker": maker_exit_stats, "taker": taker_exit_stats},
        "escudos_15s": dict(escudos_stats),
        "post_cierre_60s": post_exit_events,
    }


def imprimir_auditoria_forense_cli() -> None:
    try:
        cfg.recargar_calibracion_oos_si_cambio()
        from apoyo import micro_sensibilidad_autonoma as _msa
        _msa.auto_calibrar_sensibilidades_en_vivo(ram.ESTADO_GLOBAL, None)
    except Exception:
        pass
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo

    rep = generar_reporte_anatomico_dict()
    res = rep["resumen_global"]
    rol = rep["rol_salida"]
    mk_s, tk_s = rol["maker"], rol["taker"]
    gross_tot = round(mk_s["gross"] + tk_s["gross"], 4)
    fees_tot = round(mk_s["fees"] + tk_s["fees"], 4)

    print(f"{_C_CYAN}{'=' * 96}{_C_RESET}")
    print(f"{_C_WHITE} [FORENSIC ANATOMY INSPECTOR - verbot -a] {cfg.NOMBRE_ESTRATEGIA}{_C_RESET}")
    print(f"{_C_CYAN}{'=' * 96}{_C_RESET}")
    c_pnl = _C_GREEN if res["total_pnl_usdt"] >= 0.0 else _C_RED
    c_grs = _C_GREEN if gross_tot >= 0.0 else _C_YELLOW
    print(
        f" Global Trades: {res['trades']} (W:{res['wins']} / L:{res['losses']} / S:{res['scratches']}) | "
        f"Eff WR: {res['win_rate']:.1f}% | Gross: {c_grs}{gross_tot:+.4f}{_C_RESET} | "
        f"Fees: {_C_YELLOW}-{fees_tot:.4f}{_C_RESET} | Net: {c_pnl}{res['total_pnl_usdt']:+.4f} USDT{_C_RESET} | "
        f"UTA: {_C_WHITE}{res['real_usdt']:.4f} USDT{_C_RESET}"
    )
    print(
        f" Liquidity Exit Split -> {_C_GREEN}Maker Exits: {mk_s['trades']} "
        f"(Gross {mk_s['gross']:+.4f} / Fees -{mk_s['fees']:.4f} / Net {mk_s['net']:+.4f} USDT){_C_RESET} | "
        f"{_C_YELLOW}Taker Exits: {tk_s['trades']} (Net {tk_s['net']:+.4f} USDT){_C_RESET}"
    )

    print(f"{_C_CYAN}{'-' * 96}{_C_RESET}")
    print(f"{_C_WHITE} 1. BREAKDOWN BY CHAMPION PAIR (SIGNAL QUALITY, EDGE RATIO & LVR){_C_RESET}")
    print(
        f" {'PAIR':<19} | {'TRD':<3} | {'W/L/S':<9} | {'EFF WR':<6} | "
        f"{'AVG MFE':<7} | {'AVG MAE':<7} | {'EDGE':<5} | {'LVR':<6} | {'NET PNL'}"
    )
    print(f" {'-' * 92}")
    for par, d in rep["por_par"].items():
        tr = d["trades"]
        w, l, s = d["wins"], d["losses"], d["scratches"]
        eff_den = max(1, w + max(0, l))
        eff_wr = (w / eff_den) * 100.0 if (w + l) > 0 else 0.0
        avg_mfe = (d["mfe_sum"] / tr) if tr > 0 else 0.0
        avg_mae = (d["mae_sum"] / tr) if tr > 0 else 0.0
        edge_r = (avg_mfe / max(0.005, avg_mae)) if tr > 0 else 0.0
        avg_lvr = (d["lvr_sum"] / tr) if tr > 0 else 0.0
        col = _C_GREEN if d["pnl_usdt"] > 0.0 else (_C_RED if d["pnl_usdt"] < 0.0 else _C_WHITE)
        wls_str = f"{w}W/{l}L/{s}S"
        print(
            f" {par:<19} | {tr:<3d} | {wls_str:<9} | {eff_wr:5.1f}% | "
            f"{avg_mfe:+6.3f}% | {-avg_mae:6.3f}% | {edge_r:4.2f}x | {avg_lvr:.4f} | "
            f"{col}{d['pnl_usdt']:+8.4f} USDT{_C_RESET}"
        )

    print(f"{_C_CYAN}{'-' * 96}{_C_RESET}")
    print(f"{_C_WHITE} 2. EXIT REASON, HIGHER-ORDER WALD/L2 TELEMETRY & MFE CAPTURE MATRIX{_C_RESET}")
    mot_map = rep["por_motivo"]
    if not mot_map:
        print(f" {_C_YELLOW}[INFO] No closed trades recorded yet.{_C_RESET}")
    else:
        print(
            f" {'EXIT REASON':<22} | {'TRD':<3} | {'MKR%':<4} | {'HOLD':<6} | "
            f"{'MFE':<7} | {'ETA_MFE':<7} | {'REPEG':<5} | {'V_L2':<5} | {'NET PNL'}"
        )
        print(f" {'-' * 92}")
        for mot, dm in sorted(mot_map.items(), key=lambda x: x[1]["net_usdt"], reverse=True):
            ntr = max(1, dm["trades"])
            mkr_pct = (dm["maker_exits"] / ntr) * 100.0
            avg_h = dm["hold_sum"] / ntr
            avg_m = dm["mfe_sum"] / ntr
            avg_cap = dm["cap_sum"] / ntr
            avg_rep = dm["repeg_sum"] / ntr
            avg_vac = dm["vacio_sum"] / ntr
            col_m = _C_GREEN if dm["net_usdt"] > 0.0 else _C_RED
            print(
                f" {mot:<22} | {dm['trades']:<3d} | {mkr_pct:3.0f}% | {avg_h:5.1f}s | "
                f"{avg_m:+6.3f}% | {avg_cap:+6.2f}x | {avg_rep:4.1f}  | {avg_vac:4.2f}x | "
                f"{col_m}{dm['net_usdt']:+8.4f} USDT{_C_RESET}"
            )

    print(f"{_C_CYAN}{'-' * 96}{_C_RESET}")
    print(f"{_C_WHITE} 3. DEFENSIVE SHIELD ACCURACY (+15.0s COUNTERFACTUAL ORACLE - DEDUP EPISODES){_C_RESET}")
    esc_map = rep["escudos_15s"]
    if not esc_map:
        print(f" {_C_YELLOW}[INFO] No +15s shield interceptions recorded in current epoch yet.{_C_RESET}")
    else:
        print(
            f" {'SHIELD NAME':<22} | {'RAW/EP':<9} | {'SAVED':<5} | {'CHOP':<5} | "
            f"{'FALSE_REJ':<9} | {'PREC%':<6} | {'DEDUP SAVED'}"
        )
        print(f" {'-' * 92}")
        for esc, st_e in sorted(esc_map.items(), key=lambda x: x[1]["total"], reverse=True):
            tot_e = max(1, st_e["total"])
            ep_e = max(1, st_e.get("episodios", tot_e))
            prec_pct = ((tot_e - st_e["false_rej"]) / tot_e) * 100.0
            raw_ep_str = f"{st_e['total']}/{ep_e}"
            print(
                f" {esc:<22} | {raw_ep_str:<9} | {_C_GREEN}{st_e['saved']:<5d}{_C_RESET} | "
                f"{st_e['chop']:<5d} | {_C_YELLOW}{st_e['false_rej']:<9d}{_C_RESET} | "
                f"{prec_pct:5.1f}% | {_C_GREEN}+{st_e['usdt_saved']:.4f} USDT{_C_RESET}"
            )

    print(f"{_C_CYAN}{'-' * 96}{_C_RESET}")
    print(f"{_C_WHITE} 4. POST-EXIT MARKOUT TRACKER (+15s / +30s / +60s AFTER CLOSE){_C_RESET}")
    post_list = rep["post_cierre_60s"]
    if not post_list:
        print(f" {_C_YELLOW}[INFO] Post-exit markout tracker active (waiting for closed trades +60s).{_C_RESET}")
    else:
        ahorro_sc = sum(float(x.get("ahorro_post_scratch_usdt", 0.0)) for x in post_list)
        runners_cont = sum(1 for x in post_list if x.get("veredicto_post_cierre") == "WALD_RUNNER_CONTINUED")
        crest_opt = sum(1 for x in post_list if x.get("veredicto_post_cierre") == "WALD_CREST_OPTIMAL")
        print(
            f" Post-Scratch Capital Saved (+60s): {_C_GREEN}+{ahorro_sc:.4f} USDT{_C_RESET} | "
            f"Wald Crest Optimal: {_C_CYAN}{crest_opt}{_C_RESET} | Runner Continued: {_C_MAGENTA}{runners_cont}{_C_RESET}"
        )
        for ev_p in post_list[-6:]:
            print(
                f"   -> Trade #{ev_p.get('trade_id')} {ev_p.get('symbol')} [{ev_p.get('motivo_salida')}] "
                f"PnL={ev_p.get('pnl_usdt', 0.0):+.4f} USDT | "
                f"+15s:{ev_p.get('continuation_15s_pct', 0.0):+.3f}% "
                f"+30s:{ev_p.get('continuation_30s_pct', 0.0):+.3f}% "
                f"+60s:{ev_p.get('continuation_60s_pct', 0.0):+.3f}% ({ev_p.get('veredicto_post_cierre', '')})"
            )

    print(f"{_C_CYAN}{'-' * 96}{_C_RESET}")
    print(f"{_C_WHITE} 5. AI FORENSIC PRESCRIPTIVE DIAGNOSTIC & AUTONOMOUS WEIGHTS (TERPSICHORA V7.0){_C_RESET}")
    print(
        f"   -> Active Autonomous Weights: TP={ctrl.get('w3_tp_maker_pct', 0.0014)*100:.2f}% | "
        f"StallBE={ctrl.get('mfe_stall_harvest_pct', 0.0011)*100:.2f}% | "
        f"Unwind={ctrl.get('w4_unwind_seg', 42.0):.0f}s | "
        f"ScratchRebound={ctrl.get('sens_scratch_edad_rebote_seg', 30.0):.0f}s | "
        f"Q_Hold={ctrl.get('sens_q_l1_hold_ratio', 0.25):.2f} | "
        f"BTC_Beta={ctrl.get('w2_btc_beta', 0.32):.3f} | "
        f"KellyIA={ram.ESTADO_GLOBAL.multiplicador_kelly_ia:.2f}x"
    )
    pesos_pares = []
    for p_sym in cfg.PARES_CAMPEONES:
        c_sym = p_sym.split("/")[0]
        a_d = float(ctrl.get(f"alpha_disloc_{p_sym}", 1.0))
        w_k = float(ctrl.get(f"w_kelly_{p_sym}", 1.0))
        pesos_pares.append(f"{c_sym}(Disloc={a_d:.2f}x,Kelly={w_k:.2f}x)")
    print(f"   -> {_C_MAGENTA}[BAYESIAN PAIR MEMORY]{_C_RESET} " + " | ".join(pesos_pares))
    if tk_s["trades"] > 0:
        print(
            f"   -> {_C_YELLOW}[FEE-DRAG ALERT]{_C_RESET} {tk_s['trades']} Taker exits caused "
            f"{tk_s['net']:+.4f} USDT net drain vs {mk_s['net']:+.4f} USDT on {mk_s['trades']} Maker exits."
        )
    esc_temp = mot_map.get("ESCAPE_TEMPORAL")
    if esc_temp and esc_temp["trades"] > 0:
        print(
            f"   -> {_C_CYAN}[SELF-REMEDIATION ACTIVE]{_C_RESET} {esc_temp['trades']} ESCAPE_TEMPORAL detected "
            f"(Avg MFE {esc_temp['mfe_sum']/esc_temp['trades']:+.3f}%): elastic 54s-72s BE decompression & "
            f"7.5s multi-step scratch active."
        )
    try:
        from apoyo import micro_cinematica_l2 as _mcl_el
        from apoyo import micro_gemelo_digital_oos as _mgd_el
        from apoyo import micro_sensibilidad_autonoma as _msa_el
        from ofensiva import micro_cotizador_stoikov as _mcs_el
        from ofensiva import micro_enganche_fase as _mef_el
        from ofensiva import micro_retenedor_fill_parcial as _mrfp_el
        _ = (
            _mcl_el.calcular_curva_estacional_continua_utc,
            _mgd_el._deduplicar_eventos_15s_gemelo,
            _msa_el._deduplicar_episodios_escudo_15s,
            _msa_el._extraer_vacio_l2_evento,
            _msa_el.calcular_perfil_bayesiano_par,
            _mcs_el._contar_decimales_paso,
            _mef_el.calcular_impedancia_log_vacio_l2,
            _mef_el._obtener_multiplicador_dislocacion_par,
            _mrfp_el._obtener_contexto_l2_en_vuelo,
        )
        st.GESTOR_ESTADISTICAS.cargar_historial_disco()
        _ev_all = cargar_eventos_baul_forense()
        _mk_60 = [e for e in _ev_all if e.get("tipo_evento") == "AUDITORIA_POST_CIERRE_60S"]
        _el_w = _msa_el.calcular_pesos_elasticos_antifalso_scratch(list(st.GESTOR_ESTADISTICAS.operaciones), _mk_60)
        print(
            f"   -> {_C_GREEN}[ELASTIC ANTI-FALSE-SCRATCH]{_C_RESET} "
            f"TauScratch={_el_w['tau_scratch_seg']:.1f}s | "
            f"ZeroGiveaway<{_el_w['zero_giveaway_seg']:.0f}s (0 ticks) | "
            f"KappaWald={_el_w['kappa_wald_base']:.2f} | "
            f"Q_HoldAbort={_el_w['q_hold_abort']:.2f} | EdgeFilter: AVAX={_el_w.get('pair_disloc_mult', {}).get('AVAX/USDT:USDT', 1.0):.2f}x/{_el_w.get('pair_kelly_mult', {}).get('AVAX/USDT:USDT', 1.0):.2f}x ARB={_el_w.get('pair_disloc_mult', {}).get('ARB/USDT:USDT', 1.0):.2f}x WAL={_el_w.get('pair_disloc_mult', {}).get('WAL/USDT:USDT', 1.0):.2f}x"
        )
    except Exception:
        pass
    print(f"{_C_CYAN}{'=' * 96}{_C_RESET}")
