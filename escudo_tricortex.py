"""
Level 4 DAG: Asynchronous Tri-Cortex Groq LPU Ensemble, Structural Anti-LUNA
Collapse Filter, and Asymmetric Anti-Fragile Kelly Sizing Engine with Outlier
Convex Expansion (|Z| >= 8.0 -> gamma_outlier <= 1.15) for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import math
import os
import time
from typing import Tuple

from dotenv import load_dotenv

import config_parametros as cfg
from ofensiva import micro_conviccion_kelly as mck
from defensiva import micro_cortafuegos_contagio as mcc
import core_estado_ram as ram
import stats_tracker as st

load_dotenv()


def evaluar_filtro_anti_luna(symbol: str, caida_pct: float, ofi: float) -> Tuple[bool, str]:
    return mcc.evaluar_filtro_anti_luna(symbol, caida_pct, ofi)


def evaluar_matriz_direccional_cuantitativa(
    symbol: str,
    z_score: float,
    dp_pct: float,
    ofi: float,
    hurst: float = 0.42,
) -> str:
    return mcc.evaluar_matriz_direccional_cuantitativa(
        symbol=symbol, z_score=z_score, dp_pct=dp_pct, ofi=ofi, hurst=hurst
    )


def calcular_fraccion_kelly_antifragil(
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> float:
    return mck.calcular_fraccion_kelly_antifragil(
        z_score=z_score, ofi=ofi, hurst=hurst, side=side, symbol=symbol
    )


def calcular_dimension_kelly(
    capital_libre_usdt: float,
    z_score: float,
    ofi: float,
    hurst: float = 0.42,
    side: str = "LONG",
    symbol: str = "",
) -> Tuple[float, float, float]:
    return mck.calcular_dimension_kelly(
        capital_libre_usdt=capital_libre_usdt,
        z_score=z_score,
        ofi=ofi,
        hurst=hurst,
        side=side,
        symbol=symbol,
    )


class OrquestadorTriCortexLPU:
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
