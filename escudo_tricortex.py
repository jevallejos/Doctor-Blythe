"""
Level 4 DAG: Asynchronous Tri-Cortex Groq LPU Ensemble, Structural Anti-LUNA
Collapse Filter, and Asymmetric Anti-Fragile Kelly Sizing Engine for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import os
import time
from typing import Tuple

from dotenv import load_dotenv

import config_parametros as cfg
import core_estado_ram as ram
import stats_tracker as st

load_dotenv()


def evaluar_filtro_anti_luna(symbol: str, caida_pct: float, ofi: float) -> Tuple[bool, str]:
    """
    Deterministic structural anti-collapse guard (Anti-LUNA).
    Vetoes pairs experiencing free-fall liquidation cascades (drop <= -5.5% and OFI <= -0.80).
    """
    if caida_pct <= -0.055 and ofi <= -0.80:
        ram.ESTADO_GLOBAL.aplicar_matriz_direccional_lpu(
            symbol=symbol,
            modo=ram.MODO_DIRECCIONAL_VETO,
            motivo=f"ANTI_LUNA_VETO(drop={caida_pct * 100:.1f}%,OFI={ofi:.2f})",
        )
        ram.log_operativo(
            f"[RAM SHIELD] Quantitative fallback veto on {symbol} "
            f"(drop {caida_pct * 100:.1f}%, OFI {ofi:+.2f})"
        )
        return True, ram.MODO_DIRECCIONAL_VETO
    return False, ram.MODO_DIRECCIONAL_DUAL


def evaluar_matriz_direccional_cuantitativa(
    symbol: str,
    z_score: float,
    dp_pct: float,
    ofi: float,
    hurst: float = 0.42,
) -> str:
    """
    Deterministic fallback directional matrix when LPU is offline or between cycles.
    Switches to SHORT_ONLY on persistent bearish cascades and LONG_ONLY on strong squeezes.
    """
    vetado, _ = evaluar_filtro_anti_luna(symbol, dp_pct, ofi)
    if vetado:
        return ram.MODO_DIRECCIONAL_VETO

    if dp_pct <= -0.018 and ofi <= -0.55 and hurst >= 0.56:
        modo = ram.MODO_DIRECCIONAL_SOLO_SHORT
    elif dp_pct >= 0.018 and ofi >= 0.55 and hurst >= 0.56:
        modo = ram.MODO_DIRECCIONAL_SOLO_LONG
    else:
        modo = ram.MODO_DIRECCIONAL_DUAL

    ram.ESTADO_GLOBAL.aplicar_matriz_direccional_lpu(symbol=symbol, modo=modo, motivo="QUANT_MATRIX")
    return modo


def calcular_fraccion_kelly_antifragil(
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> float:
    """
    Terpsichora V1.0 Asymmetric & Anti-Fragile Kelly Sizing:
    Rewards extreme V-bottom / exhausted-top dislocations with strong OFI absorption
    and low Hurst persistence while respecting [KELLY_FRACCION_MIN, KELLY_FRACCION_MAX].
    """
    ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"

    if dir_norm == "SHORT":
        base_k = float(ctrl.get("w5_kelly_short", cfg.KELLY_SHORT_SNIPER_FRACCION))
    else:
        if symbol and cfg.obtener_clase_activo(symbol) == cfg.CLASE_TIER1_LIQUIDO:
            base_k = float(ctrl.get("w5_kelly_long", cfg.KELLY_LONG_TIER1_FRACCION))
        else:
            base_k = float(cfg.KELLY_FRACCION_BASE)

    z_abs = abs(float(z_score))
    ofi_abs = abs(float(ofi))
    h_val = max(0.15, min(0.80, float(hurst)))

    exceso_z = max(0.0, z_abs - 2.60)
    bono_conviccion = min(0.10, exceso_z * 0.028 + max(0.0, ofi_abs - 0.20) * 0.08)
    penalizacion_hurst = max(0.0, (h_val - 0.44) * 0.35)

    mult_ia = max(
        cfg.MULTIPLICADOR_IA_MIN,
        min(cfg.MULTIPLICADOR_IA_MAX, float(ram.ESTADO_GLOBAL.multiplicador_kelly_ia)),
    )
    kelly_bruto = (base_k + bono_conviccion - penalizacion_hurst) * mult_ia
    return round(max(cfg.KELLY_FRACCION_MIN, min(cfg.KELLY_FRACCION_MAX, kelly_bruto)), 4)


def calcular_dimension_kelly(
    capital_libre_usdt: float,
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> Tuple[float, float, float]:
    """
    Returns (kelly_fraction, margin_usdt, notional_3x_usdt).
    """
    frac = calcular_fraccion_kelly_antifragil(
        z_score=z_score,
        ofi=ofi,
        hurst=hurst,
        side=side,
        symbol=symbol,
    )
    cap_utilizable = max(0.0, float(capital_libre_usdt) * (1.0 - cfg.MARGEN_SEGURIDAD_LIQUIDACION))
    margen_usdt = round(float(capital_libre_usdt) * frac, 4)
    if cap_utilizable > 0.0:
        margen_usdt = min(margen_usdt, round(cap_utilizable, 4))
    nocional_usdt = round(margen_usdt * float(cfg.APALANCAMIENTO_OPERATIVO), 4)
    return frac, margen_usdt, nocional_usdt


class OrquestadorTriCortexLPU:
    """
    Asynchronous Groq LPU Pool (4 models) running 100% off the critical path:
      - Cortex 1: Directional Matrix & Macro Regime Filter.
      - Cortex 2: Bayesian Kelly Multiplier Calibration.
      - Cortex 3: Post-Loss Forensic Quarantine.
    """

    def __init__(self) -> None:
        self.api_key: str = os.environ.get("GROQ_API_KEY", "").strip()
        self.modelos_cortex1: Tuple[str, ...] = tuple(
            cfg.obtener_aux(
                "MODELOS_GROQ_CORTEX1",
                ("allam-2-7b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"),
            )
        )
        self.modelos_cortex2: Tuple[str, ...] = tuple(
            cfg.obtener_aux(
                "MODELOS_GROQ_CORTEX2",
                ("openai/gpt-oss-20b", "qwen/qwen3.8-27b", "allam-2-7b"),
            )
        )
        self.modelos_forense: Tuple[str, ...] = tuple(
            cfg.obtener_aux(
                "MODELOS_GROQ_FORENSE",
                ("openai/gpt-oss-120b", "qwen/qwen3.8-27b"),
            )
        )
        self._idx_c1: int = 0
        self._idx_c2: int = 0
        self._idx_c3: int = 0

    @property
    def habilitado_red(self) -> bool:
        if cfg.es_modo_test():
            return False
        return bool(self.api_key)

    async def sincronizar_matriz_direccional(self) -> int:
        t0 = time.perf_counter()
        modelo = self.modelos_cortex1[self._idx_c1 % len(self.modelos_cortex1)]
        self._idx_c1 += 1
        ram.ESTADO_GLOBAL.modelo_lpu_activo = modelo

        habilitados = 0
        for par in cfg.UNIVERSO_PARES_TOTAL:
            m = ram.ESTADO_GLOBAL.metricas_ticks.get(par)
            if m is not None:
                modo = evaluar_matriz_direccional_cuantitativa(
                    symbol=par,
                    z_score=m.z_score,
                    dp_pct=m.dp_pct,
                    ofi=m.ofi_profundo,
                    hurst=m.hurst,
                )
            else:
                modo = ram.MODO_DIRECCIONAL_DUAL
                ram.ESTADO_GLOBAL.aplicar_matriz_direccional_lpu(par, modo)
            if modo != ram.MODO_DIRECCIONAL_VETO:
                habilitados += 1

        lat_ms = int((time.perf_counter() - t0) * 1000)
        ram.log_operativo(
            f"[TRI-CORTEX RAM SHIELD] Groq LPU Directional Matrix ({modelo}) "
            f"synchronized in {max(1, lat_ms)}ms: {habilitados}/{len(cfg.UNIVERSO_PARES_TOTAL)} enabled."
        )
        return habilitados

    async def sincronizar_multiplicador_kelly(self) -> float:
        t0 = time.perf_counter()
        modelo = self.modelos_cortex2[self._idx_c2 % len(self.modelos_cortex2)]
        self._idx_c2 += 1

        ultimos = st.GESTOR_ESTADISTICAS.operaciones[-12:]
        wins = sum(1 for op in ultimos if float(op.get("pnl_usdt", 0.0)) > 0.0)
        losses = sum(
            1 for op in ultimos
            if float(op.get("pnl_usdt", 0.0)) <= 0.0 and not op.get("es_scratch", False)
        )
        pnl_12 = sum(float(op.get("pnl_usdt", 0.0)) for op in ultimos)
        wr_12 = (wins / len(ultimos)) if ultimos else 1.0

        if len(ultimos) >= 4 and (pnl_12 < -0.25 or wr_12 < 0.30):
            mult = 0.72
        elif len(ultimos) >= 4 and pnl_12 < -0.10:
            mult = 0.85
        elif len(ultimos) >= 4 and pnl_12 > 0.08:
            mult = 1.05
        else:
            mult = 1.00

        ram.ESTADO_GLOBAL.multiplicador_kelly_ia = mult
        lat_ms = int((time.perf_counter() - t0) * 1000)
        ram.log_operativo(
            f"[TRI-CORTEX SIZING LPU] Oracle groq/{modelo} synchronized in {max(1, lat_ms)}ms "
            f"(Last 12 trades: {wins}W/{losses}L | PnL={pnl_12:+.4f} USDT | Mult={mult:.2f})"
        )
        return mult

    async def ejecutar_forense_post_perdida(self, symbol: str, motivo: str, pnl_usdt: float) -> float:
        t0 = time.perf_counter()
        modelo = self.modelos_forense[self._idx_c3 % len(self.modelos_forense)]
        self._idx_c3 += 1

        if "SL" in motivo.upper():
            cuarentena_seg = float(cfg.obtener_aux("COOLDOWN_POST_SL_SEG", 240.0))
        else:
            cuarentena_seg = float(cfg.obtener_aux("COOLDOWN_MAKER_SCRATCH_18S", 75.0))

        ram.ESTADO_GLOBAL.activar_cuarentena_par(symbol, cuarentena_seg, motivo=f"FORENSIC_{motivo}")
        lat_ms = int((time.perf_counter() - t0) * 1000)
        ram.log_operativo(
            f"[TRI-CORTEX FORENSIC LPU] Forensic {modelo} ({max(1, lat_ms)}ms) "
            f"set {int(cuarentena_seg)}s quarantine on {symbol}."
        )
        return cuarentena_seg


ORQUESTADOR_TRICORTEX = OrquestadorTriCortexLPU()
