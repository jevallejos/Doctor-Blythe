# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #1: Motores Matematicos L2 de Variacion Bipower (VentanaZ)
Desacoplada por Par, Curva Estacional Elastica 24h UTC de 5 Polos Gaussianos,
OFI Profundo de 5 Niveles, Exponente de Hurst con Correccion de Muestra Finita,
Cinematica de Lyapunov, Desequilibrio de Cancelacion L1 y Entropia Temporal LOB
para HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
import collections
import datetime
import math
import time
from typing import Deque, List, Optional, Tuple

import config_parametros as cfg

_TZ_UTC = datetime.timezone.utc

_CURVA_ESTACIONAL_24H_UTC: Tuple[float, ...] = (
    0.58, 0.55, 0.52, 0.48, 0.45, 0.46,
    0.52, 0.64, 0.72, 0.75, 0.70, 0.66,
    0.74, 0.88, 0.94, 0.92, 0.85, 0.76,
    0.68, 0.64, 0.62, 0.60, 0.59, 0.58,
)


def calcular_curva_estacional_continua_utc(timestamp_utc: Optional[float] = None) -> float:
    """
    Evalua la intensidad estacional continua S_UTC(t) in [0.44, 0.96] combinando
    la interpolacion horaria discreta con los 5 polos Gaussianos de liquidez
    intradia (00:00 Asia Open, 04:50 Asia Mid, 08:00 London Open, 13:45 NY Open,
    16:00 London Close).
    """
    ts = float(timestamp_utc) if timestamp_utc is not None else time.time()
    dt_utc = datetime.datetime.fromtimestamp(ts, _TZ_UTC)
    h_cont = dt_utc.hour + (dt_utc.minute / 60.0) + (dt_utc.second / 3600.0)
    base_h = _CURVA_ESTACIONAL_24H_UTC[dt_utc.hour % 24]

    polos = (
        (0.00, 0.14, 1.35),
        (4.83, 0.08, 1.20),
        (8.00, 0.16, 1.40),
        (13.75, 0.24, 1.55),
        (16.00, 0.18, 1.45),
    )
    pulso_gauss = 0.0
    for mu_h, amp, width in polos:
        diff = min(abs(h_cont - mu_h), 24.0 - abs(h_cont - mu_h))
        pulso_gauss += amp * math.exp(-0.5 * ((diff / width) ** 2))

    s_cont = (0.72 * base_h) + (0.28 * min(0.98, 0.46 + pulso_gauss))
    return round(max(0.44, min(0.96, s_cont)), 4)


def calcular_percentil_intradia_24h(
    volatilidad_bv: float,
    timestamp_utc: Optional[float] = None,
    symbol: str = "",
    volatilidad_bv_raw: float = 0.0,
) -> Tuple[float, str]:
    """
    Calcula el percentil intradia elastico P_24h in [0.05, 0.99] desacoplando
    la escala natural de cada par (High-Beta vs Tier-1) del piso del Z-Score.
    Si se provee symbol y/o volatilidad_bv_raw, normaliza respecto al perfil
    intrinseco (sigma_floor, sigma_ref, sigma_ceil) del par para erradicar el
    congelamiento en 0.00055 de ARB, AVAX, TAO, XRP y WAL.
    """
    base_estacional = calcular_curva_estacional_continua_utc(timestamp_utc)
    if symbol and hasattr(cfg, "obtener_perfil_elasticidad_bv"):
        s_floor, s_ref, s_ceil = cfg.obtener_perfil_elasticidad_bv(symbol)
        sigma_eval = float(volatilidad_bv_raw) if volatilidad_bv_raw > 0.0 else float(volatilidad_bv)
        sigma_acotada = max(s_floor, min(s_ceil, sigma_eval))
        ratio_vol = min(1.55, max(0.52, sigma_acotada / max(1e-6, s_ref)))
    else:
        sigma_eval = float(volatilidad_bv_raw) if volatilidad_bv_raw > 0.0 else float(volatilidad_bv)
        sigma_ref = max(sigma_eval, cfg.VOLATILIDAD_BV_PISO_MIN)
        ratio_vol = min(1.45, max(0.65, sigma_ref / 0.00075))

    percentil = max(
        cfg.PERCENTIL_DIA_MIN,
        min(cfg.PERCENTIL_DIA_MAX, base_estacional * ratio_vol),
    )
    etiqueta = f"P{int(round(percentil * 100)):02d}_ELASTICO"
    return round(percentil, 4), etiqueta


def calcular_multiplicador_elastico_par(
    percentil_24h: float,
    alpha_disloc_par: float = 1.0,
    es_high_beta: bool = True,
) -> float:
    """
    Operador Elastico Homogeneo E_t(sym) = alpha_disloc(sym) * phi(P_24h):
    - Preserva estrictamente la no-regresion sobre los pisos SCAR-LOCK cuando
      alpha_disloc_par >= 1.00.
    - En regimenes de calma intradia (P_24h < 0.45) en pares Tier-1, permite
      capturar reversiones limpias sin ruido; en regimenes de tormenta (P_24h > 0.80),
      expande la exigencia de excursion para evitar cuchillos cayendo.
    """
    p_clamped = max(cfg.PERCENTIL_DIA_MIN, min(cfg.PERCENTIL_DIA_MAX, float(percentil_24h)))
    alpha_safe = max(1.00, min(1.40, float(alpha_disloc_par or 1.0)))
    if es_high_beta:
        phi_p = 0.94 + (0.18 * (p_clamped - 0.50))
        return round(max(0.95, min(1.48, alpha_safe * phi_p)), 4)
    phi_t1 = 0.92 + (0.20 * (p_clamped - 0.50))
    return round(max(0.90, min(1.45, alpha_safe * phi_t1)), 4)


class VentanaZ:
    """
    Jump-Robust Bipower Variation Z-Score & Horizon-Synchronized Excursion Engine
    with O(1) Bipower Product Ring Buffer, Unclamped Raw Bipower Tracking
    (volatilidad_bv_raw), and Boxcar-EMA Sign Coherence.
    """

    def __init__(
        self,
        maxlen: int = cfg.VENTANA_Z_TICKS,
        piso_volatilidad: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    ) -> None:
        self.maxlen: int = max(30, int(maxlen))
        self.piso_volatilidad: float = max(0.00035, float(piso_volatilidad))
        self.precios: Deque[float] = collections.deque(maxlen=self.maxlen)
        self.retornos: Deque[float] = collections.deque(maxlen=self.maxlen)
        self.pares_bv: Deque[float] = collections.deque(maxlen=self.maxlen)
        self.ema_rapida: float = 0.0
        self.ema_macro: float = 0.0
        self.ema_macro_prev: float = 0.0
        self.volatilidad_bv: float = self.piso_volatilidad
        self.volatilidad_bv_raw: float = self.piso_volatilidad
        self.sigma_ema_par: float = 0.0
        self.z_score: float = 0.0
        self.dp_pct: float = 0.0

    def actualizar(self, precio: float, timestamp: Optional[float] = None) -> Tuple[float, float, float]:
        p = float(precio)
        if p <= 0.0:
            return self.z_score, self.dp_pct, self.volatilidad_bv

        if self.precios:
            prev = self.precios[-1]
            ret = (p - prev) / prev if prev > 0.0 else 0.0
            if abs(ret) > 1e-9:
                abs_ret = abs(ret)
                if self.retornos:
                    self.pares_bv.append(abs_ret * abs(self.retornos[-1]))
                self.retornos.append(ret)
        self.precios.append(p)

        alpha_fast = 2.0 / (cfg.EMA_RAPIDA_TICKS + 1.0)
        alpha_macro = 2.0 / (cfg.EMA_MACRO_TICKS + 1.0)
        if self.ema_rapida <= 0.0:
            self.ema_rapida = p
            self.ema_macro = p
            self.ema_macro_prev = p
        else:
            self.ema_rapida = (alpha_fast * p) + ((1.0 - alpha_fast) * self.ema_rapida)
            self.ema_macro_prev = self.ema_macro
            self.ema_macro = (alpha_macro * p) + ((1.0 - alpha_macro) * self.ema_macro)

        if len(self.precios) < 4:
            return 0.0, 0.0, self.volatilidad_bv

        p_base = self.precios[0]
        self.dp_pct = (p - p_base) / p_base if p_base > 0.0 else 0.0

        n_bv = len(self.pares_bv)
        if n_bv >= 3:
            media_bv = (math.pi / 2.0) * (sum(self.pares_bv) / n_bv)
            sigma_tick = math.sqrt(max(0.0, media_bv))
            n_rets = len(self.retornos)
            sigma_horizonte = sigma_tick * math.sqrt(min(12.0, float(n_rets)))
            self.volatilidad_bv_raw = round(max(0.00008, min(0.00250, sigma_horizonte)), 6)
            if self.sigma_ema_par <= 0.0:
                self.sigma_ema_par = self.volatilidad_bv_raw
            else:
                self.sigma_ema_par = round((0.02 * self.volatilidad_bv_raw) + (0.98 * self.sigma_ema_par), 6)
            self.volatilidad_bv = max(self.piso_volatilidad, min(0.00110, sigma_horizonte))
        else:
            self.volatilidad_bv_raw = max(0.00025, self.volatilidad_bv_raw)
            self.volatilidad_bv = max(self.piso_volatilidad, cfg.VOLATILIDAD_BV_PISO_MIN)

        dp_ema = (p - self.ema_rapida) / self.ema_rapida if self.ema_rapida > 0.0 else self.dp_pct
        if (self.dp_pct * dp_ema) < 0.0:
            desviacion_compuesta = (0.45 * self.dp_pct) + (0.55 * dp_ema)
        else:
            desviacion_compuesta = (0.72 * self.dp_pct) + (0.28 * dp_ema)

        self.z_score = round(desviacion_compuesta / self.volatilidad_bv, 4)
        return self.z_score, round(self.dp_pct, 6), round(self.volatilidad_bv, 6)


def calcular_ofi_profundo(
    bids_prev: List[Tuple[float, float]],
    asks_prev: List[Tuple[float, float]],
    bids_curr: List[Tuple[float, float]],
    asks_curr: List[Tuple[float, float]],
) -> float:
    pesos = cfg.OFI_PESOS_NIVELES
    niveles = min(cfg.OFI_NIVELES_PROFUNDO, len(pesos))
    num = 0.0
    den = 0.0
    n_bp = len(bids_prev)
    n_ap = len(asks_prev)
    n_bc = len(bids_curr)
    n_ac = len(asks_curr)

    for idx in range(niveles):
        w = pesos[idx]
        bp, bq_p = bids_prev[idx] if idx < n_bp else (0.0, 0.0)
        ap, aq_p = asks_prev[idx] if idx < n_ap else (0.0, 0.0)
        bc, bq_c = bids_curr[idx] if idx < n_bc else (0.0, 0.0)
        ac, aq_c = asks_curr[idx] if idx < n_ac else (0.0, 0.0)

        if bc > bp:
            delta_b = bq_c
        elif bc == bp:
            delta_b = bq_c - bq_p
        else:
            delta_b = -bq_p

        if ac < ap:
            delta_a = aq_c
        elif ac == ap:
            delta_a = aq_c - aq_p
        else:
            delta_a = -aq_p

        ofi_lvl = delta_b - delta_a
        flujo_activo = abs(delta_b) + abs(delta_a)
        reg_liquidez = (bq_c + aq_c) * 0.035
        num += w * ofi_lvl
        den += w * max(flujo_activo + reg_liquidez, 1e-9)

    if den <= 1e-9:
        return 0.0
    est = max(-1.0, min(1.0, num / den))
    return round(est, 4)


def calcular_exponente_hurst(precios_activos: List[float], z_score_actual: float = 0.0) -> float:
    if len(precios_activos) < 8:
        return 0.40
    cambios = [precios_activos[0]]
    for p in precios_activos[1:]:
        if abs(p - cambios[-1]) > 1e-12:
            cambios.append(p)
    if len(cambios) < 8:
        return 0.40

    ventana = cambios[-max(12, cfg.HURST_VENTANA_TICKS):]
    rets = [
        math.log(ventana[i] / ventana[i - 1])
        for i in range(1, len(ventana))
        if ventana[i] > 0.0 and ventana[i - 1] > 0.0
    ]
    if len(rets) < 6:
        return 0.40

    abs_rets = sorted(abs(r) for r in rets if abs(r) > 0.0)
    med = abs_rets[len(abs_rets) // 2] if abs_rets else 1e-4
    cap = max(med * 2.5, 1e-5)
    r_clip = [max(-cap, min(cap, r)) for r in rets]

    tramo_local = r_clip[-16:]
    n_loc = len(tramo_local)
    media_local = sum(tramo_local) / n_loc
    frenado_activo = (r_clip[-1] * media_local) <= 0.0 or abs(r_clip[-1]) < abs(media_local) * 0.65

    serie_eval = [r - media_local for r in tramo_local] if frenado_activo else [r - (0.35 * media_local) for r in r_clip]
    denom = sum(r * r for r in serie_eval)
    if denom <= 1e-15:
        return 0.38

    num = sum(serie_eval[i] * serie_eval[i - 1] for i in range(1, len(serie_eval)))
    rho1_raw = max(-0.45, min(0.75, num / denom))
    if not frenado_activo and n_loc >= 6:
        rho1 = min(0.75, rho1_raw + (1.0 - (rho1_raw * rho1_raw)) / (2.0 * n_loc))
    else:
        rho1 = rho1_raw
    h_raw = 0.50 + (0.50 * (math.log(max(0.25, 1.0 + rho1)) / math.log(2.0)))

    if len(rets) >= 5 and (all(r > 0.0 for r in rets[-5:]) or all(r < 0.0 for r in rets[-5:])):
        h_raw = max(h_raw, 0.56)
    elif len(rets) >= 8 and not frenado_activo:
        pos_8 = sum(1 for r in rets[-8:] if r > 0.0)
        neg_8 = sum(1 for r in rets[-8:] if r < 0.0)
        if max(pos_8, neg_8) >= 7:
            h_raw = max(h_raw, 0.495)

    if z_score_actual >= cfg.Z_SCORE_IGNICION_SHORT_VETO and ventana[-1] >= max(ventana[:-1]):
        h_raw = max(h_raw, 0.58)

    return round(max(0.20, min(0.80, h_raw)), 4)


def calcular_aceleracion_lyapunov(precios: List[float], spread_pct: float = 0.0) -> float:
    if len(precios) < 5:
        return 0.0
    ventana = precios[-max(5, cfg.LYAPUNOV_VENTANA_TICKS):]
    p0, p_mid, p_end = ventana[0], ventana[len(ventana) // 2], ventana[-1]
    if p0 <= 0.0 or p_mid <= 0.0:
        return 0.0
    v1 = (p_mid - p0) / p0
    v2 = (p_end - p_mid) / p_mid
    acel = v2 - v1

    umbral_tick = max(spread_pct * 1.25, 0.00042)
    if acel < 0.0 and (v2 >= 0.0 or (abs(v2) <= umbral_tick and abs(v2) <= abs(v1))):
        if v1 > umbral_tick and v2 <= 0.0:
            return round(acel, 6)
        return round(max(acel, cfg.LYAPUNOV_ACEL_UMBRAL_FRENADO * 0.4), 6)
    return round(acel, 6)


def calcular_desequilibrio_cancelacion_l1(
    bids_prev: List[Tuple[float, float]],
    asks_prev: List[Tuple[float, float]],
    bids_curr: List[Tuple[float, float]],
    asks_curr: List[Tuple[float, float]],
) -> Tuple[float, float]:
    """
    Mejora de Frontera #2 (arXiv:2502.17417):
    Calcula el desequilibrio estatico de la punta L1 (imb_l1 in [-1, +1]) y el
    diferencial neto de cancelaciones agresivas en L1 (SC+ vs BC-).
    """
    if not bids_curr or not asks_curr:
        return 0.0, 0.0
    bc, bq_c = bids_curr[0]
    ac, aq_c = asks_curr[0]
    denom_l1 = max(1e-9, bq_c + aq_c)
    imb_l1 = round(max(-1.0, min(1.0, (bq_c - aq_c) / denom_l1)), 4)

    if not bids_prev or not asks_prev:
        return imb_l1, 0.0
    bp, bq_p = bids_prev[0]
    ap, aq_p = asks_prev[0]

    bc_minus = max(0.0, bq_p - bq_c) if abs(bc - bp) <= 1e-12 else (bq_p if bc < bp else 0.0)
    sc_plus = max(0.0, aq_p - aq_c) if abs(ac - ap) <= 1e-12 else (aq_p if ac > ap else 0.0)
    denom_c = max(1e-9, sc_plus + bc_minus + (0.10 * denom_l1))
    cancel_net = round(max(-1.0, min(1.0, (sc_plus - bc_minus) / denom_c)), 4)
    return imb_l1, cancel_net


def calcular_irreversibilidad_temporal_lob(
    precios_activos: List[float],
    ofi_actual: float = 0.0,
) -> float:
    """
    Mejora de Frontera #3 (arXiv:2610.16151):
    Indice de Irreversibilidad Temporal (Delta S_LOB in [0.0, 1.0]) combinando
    divergencia de Kullback-Leibler de rachas Markovianas y asimetria energetica de saltos.
    """
    if len(precios_activos) < 6:
        return 0.0
    ventana = precios_activos[-14:]
    signos: List[int] = []
    energia_pos = 1e-9
    energia_neg = 1e-9
    for i in range(1, len(ventana)):
        dp = ventana[i] - ventana[i - 1]
        if abs(dp) > 1e-12:
            signos.append(1 if dp > 0.0 else -1)
            if dp > 0.0:
                energia_pos += abs(dp)
            else:
                energia_neg += abs(dp)
    if len(signos) < 4:
        return 0.0

    n_pp = 0.5
    n_mm = 0.5
    n_pm = 0.5
    n_mp = 0.5
    for i in range(1, len(signos)):
        s0, s1 = signos[i - 1], signos[i]
        if s0 > 0 and s1 > 0:
            n_pp += 1.0
        elif s0 < 0 and s1 < 0:
            n_mm += 1.0
        elif s0 > 0 and s1 < 0:
            n_pm += 1.0
        else:
            n_mp += 1.0
    tot = n_pp + n_mm + n_pm + n_mp
    p_pp, p_mm, p_pm, p_mp = n_pp / tot, n_mm / tot, n_pm / tot, n_mp / tot

    kl_cruce = (p_pm - p_mp) * math.log(p_pm / p_mp)
    kl_racha = 0.38 * (p_pp - p_mm) * math.log(p_pp / p_mm)
    e_tot = energia_pos + energia_neg
    q_pos, q_neg = energia_pos / e_tot, energia_neg / e_tot
    kl_energia = 0.22 * (q_pos - q_neg) * math.log(q_pos / q_neg)
    acople_ofi = 0.15 * abs(float(ofi_actual)) if (signos[-1] * ofi_actual) > 0.0 else 0.0

    entropia = max(0.0, min(1.0, kl_cruce + kl_racha + kl_energia + acople_ofi))
    return round(entropia, 4)


def calcular_perfil_muros_vacio_l2(
    bids_full: List[Tuple[float, float]],
    asks_full: List[Tuple[float, float]],
    mid: float,
) -> Tuple[float, float, float, float]:
    """
    Escanea hasta los primeros 25 niveles del stream Bybit orderbook.50 en O(1):
    1. Detecta el primer Muro de Liquidez (Liquidity Wall >= 2.8x profundidad media
       y >= 28% del volumen Top-5) dentro del corredor de cosecha [0.10%, 0.45%].
    2. Calcula la Razon de Vacio Profundo (Vacuum Ratio) entre el soporte L1..L10
       y la resistencia L2..L15 opuesta para dejar correr runners sin resistencia.
    Retorna (muro_ask_px, muro_bid_px, vacio_long_ratio, vacio_short_ratio).
    """
    if mid <= 0.0 or (len(bids_full) <= 2 and len(asks_full) <= 2):
        return 0.0, 0.0, 1.0, 1.0

    b_slice = bids_full[:25]
    a_slice = asks_full[:25]
    top5_bid_v = sum(q for _, q in b_slice[:5])
    top5_ask_v = sum(q for _, q in a_slice[:5])
    mean_bid_v = (sum(q for _, q in b_slice) / len(b_slice)) if b_slice else 0.0
    mean_ask_v = (sum(q for _, q in a_slice) / len(a_slice)) if a_slice else 0.0

    umbral_muro_ask = max(mean_ask_v * 2.8, top5_ask_v * 0.28, 1e-9)
    umbral_muro_bid = max(mean_bid_v * 2.8, top5_bid_v * 0.28, 1e-9)

    muro_ask_px = 0.0
    for px_a, qty_a in a_slice:
        dist_a = (px_a - mid) / mid
        if dist_a < 0.00095:
            continue
        if dist_a > 0.0045:
            break
        if qty_a >= umbral_muro_ask:
            muro_ask_px = float(px_a)
            break

    muro_bid_px = 0.0
    for px_b, qty_b in b_slice:
        dist_b = (mid - px_b) / mid
        if dist_b < 0.00095:
            continue
        if dist_b > 0.0045:
            break
        if qty_b >= umbral_muro_bid:
            muro_bid_px = float(px_b)
            break

    b_sup = b_slice[:10]
    a_sup = a_slice[:10]
    if len(b_slice) > 15 or len(a_slice) > 15:
        a_res = a_slice[1:15] if len(a_slice) > 1 else a_slice
        b_res = b_slice[1:15] if len(b_slice) > 1 else b_slice
        soporte_bid_10 = sum(q for _, q in b_sup) / max(1, len(b_sup))
        resistencia_ask_2_15 = sum(q for _, q in a_res) / max(1, len(a_res))
        soporte_ask_10 = sum(q for _, q in a_sup) / max(1, len(a_sup))
        resistencia_bid_2_15 = sum(q for _, q in b_res) / max(1, len(b_res))
    else:
        soporte_bid_10 = sum(q for _, q in b_sup)
        resistencia_ask_2_15 = sum(q for _, q in a_slice)
        soporte_ask_10 = sum(q for _, q in a_sup)
        resistencia_bid_2_15 = sum(q for _, q in b_slice)

    vacio_long = (
        round(max(0.20, min(3.00, soporte_bid_10 / max(1e-9, resistencia_ask_2_15))), 4)
        if resistencia_ask_2_15 > 0.0
        else 1.0
    )
    vacio_short = (
        round(max(0.20, min(3.00, soporte_ask_10 / max(1e-9, resistencia_bid_2_15))), 4)
        if resistencia_bid_2_15 > 0.0
        else 1.0
    )
    return muro_ask_px, muro_bid_px, vacio_long, vacio_short
