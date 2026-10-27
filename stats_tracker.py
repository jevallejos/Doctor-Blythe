"""
Level 3 DAG: Transactional Black Box Ledger (tribrain_stats_v1.jsonl),
1:1 Bybit UTA Balance Parity Engine, and Continuous Limit Order Book
Loss-Versus-Rebalancing (LOB LVR) Tracker for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import datetime
import json
import math
import pathlib
import time
from typing import Any, Dict, List, Optional

import config_parametros as cfg
from apoyo import micro_paridad_lvr_uta as mpl
import core_estado_ram as ram

_TZ_UTC = datetime.timezone.utc


def calcular_lvr_instantaneo(
    precio_entrada: float,
    precio_salida: float,
    duracion_seg: float,
    volatilidad_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    es_maker: bool = True,
) -> float:
    return mpl.calcular_lvr_instantaneo(
        precio_entrada=precio_entrada,
        precio_salida=precio_salida,
        duracion_seg=duracion_seg,
        volatilidad_bv=volatilidad_bv,
        es_maker=es_maker,
    )


class GestorEstadisticasHFT:
    """
    Immutable JSONL Ledger and 1:1 Bybit UTA Parity Synchronizer.
    """

    def __init__(self, ruta_jsonl: Optional[pathlib.Path] = None) -> None:
        self._ruta_custom: Optional[pathlib.Path] = ruta_jsonl
        self.operaciones: List[Dict[str, Any]] = []
        self.base_balance_usdt: float = cfg.CAPITAL_BASE_HISTORICO_USDT
        self.ajuste_paridad_usdt: float = 0.0
        self.real_uta_balance_usdt: float = cfg.CAPITAL_BASE_HISTORICO_USDT
        self._cargado: bool = False
        if not cfg.es_modo_test():
            self.cargar_historial_disco()

    @property
    def ruta_ledger(self) -> pathlib.Path:
        if self._ruta_custom is not None:
            return self._ruta_custom
        return cfg.obtener_ruta_archivo("ARCHIVO_STATS_JSONL")

    def reiniciar_memoria_test(self, base_usdt: float = 9.8700, real_usdt: float = 9.8662) -> None:
        self.operaciones.clear()
        self.base_balance_usdt = float(base_usdt)
        self.real_uta_balance_usdt = float(real_usdt)
        self.ajuste_paridad_usdt = 0.0
        self._cargado = True

    def cargar_historial_disco(self) -> int:
        self.operaciones.clear()
        self.ajuste_paridad_usdt = 0.0
        ruta = self.ruta_ledger
        if not ruta.exists():
            self._cargado = True
            return 0
        try:
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                linea_s = linea.strip()
                if not linea_s:
                    continue
                obj = json.loads(linea_s)
                tipo = obj.get("tipo_registro", "TRADE")
                if tipo == "PARITY_SYNC":
                    self.ajuste_paridad_usdt += float(obj.get("delta_paridad_usdt", 0.0))
                else:
                    self.operaciones.append(obj)
        except Exception:
            pass
        self._cargado = True
        return len(self.operaciones)

    def sincronizar_paridad_uta(self, saldo_real_bybit: float, silencioso: bool = False) -> float:
        if saldo_real_bybit <= 0.0:
            return 0.0
        self.real_uta_balance_usdt = float(saldo_real_bybit)
        ram.ESTADO_GLOBAL.capital_total_uta = float(saldo_real_bybit)

        pnl_acum = sum(float(op.get("pnl_usdt", 0.0)) for op in self.operaciones)
        balance_contable = self.base_balance_usdt + pnl_acum + self.ajuste_paridad_usdt
        delta = round(self.real_uta_balance_usdt - balance_contable, 4)

        if abs(delta) >= 0.0001:
            self.ajuste_paridad_usdt = round(self.ajuste_paridad_usdt + delta, 4)
            nuevo_balance = self.base_balance_usdt + pnl_acum + self.ajuste_paridad_usdt
            if not cfg.es_modo_test():
                evento = {
                    "tipo_registro": "PARITY_SYNC",
                    "timestamp": round(time.time(), 3),
                    "delta_paridad_usdt": delta,
                    "balance_uta_real": round(self.real_uta_balance_usdt, 4),
                    "balance_contable": round(nuevo_balance, 4),
                }
                try:
                    with open(self.ruta_ledger, mode="a", encoding="utf-8") as fh:
                        fh.write(json.dumps(evento, ensure_ascii=True) + "\n")
                except Exception:
                    pass
            if not silencioso:
                ram.log_operativo(
                    f"[BLACK BOX 1:1] UTA parity synchronized to 1e-4 without mutating trade PnL "
                    f"(Funding/Parity Adjustment: {delta:+.4f} USDT -> "
                    f"Balance {nuevo_balance:.4f} == {self.real_uta_balance_usdt:.4f} USDT)."
                )
        return delta

    def registrar_operacion(
        self,
        symbol: str,
        side: str,
        precio_entrada: float,
        precio_salida: float,
        contratos: float,
        pnl_usdt: float,
        pnl_pct: float,
        motivo_salida: str,
        duracion_seg: float,
        fees_usdt: float = 0.0,
        es_entrada_maker: bool = True,
        es_salida_maker: bool = True,
        mfe_pct: float = 0.0,
        mae_pct: float = 0.0,
        volatilidad_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
        vector_entrada: Optional[Dict[str, Any]] = None,
        trayectoria_pnl: Optional[Dict[str, float]] = None,
        persistir_disco: bool = True,
    ) -> Dict[str, Any]:
        ahora = time.time()
        trade_id = len(self.operaciones) + 1
        map_usdt = round(abs(contratos * precio_entrada), 4)
        es_scratch = (
            "SCRATCH" in motivo_salida.upper()
            or ("UNWIND" in motivo_salida.upper() and abs(pnl_pct) <= 0.0014 and pnl_usdt <= 0.0)
        )
        resultado = "WIN" if pnl_usdt > 0.0 else ("SCRATCH" if es_scratch else "LOSS")
        lvr_trade = calcular_lvr_instantaneo(
            precio_entrada=precio_entrada,
            precio_salida=precio_salida,
            duracion_seg=duracion_seg,
            volatilidad_bv=volatilidad_bv,
            es_maker=(es_entrada_maker and es_salida_maker),
        )

        registro: Dict[str, Any] = {
            "tipo_registro": "TRADE",
            "trade_id": trade_id,
            "timestamp": round(ahora, 3),
            "fecha_utc": datetime.datetime.fromtimestamp(ahora, _TZ_UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "estrategia": cfg.CODIGO_ESTRATEGIA,
            "symbol": symbol,
            "side": "LONG" if side.upper() in ("BUY", "LONG") else "SHORT",
            "resultado": resultado,
            "es_scratch": es_scratch,
            "motivo_salida": motivo_salida,
            "precio_entrada": precio_entrada,
            "precio_salida": precio_salida,
            "contratos": contratos,
            "map_usdt": map_usdt,
            "pnl_usdt": round(float(pnl_usdt), 4),
            "pnl_pct": round(float(pnl_pct) * 100.0, 4),
            "fees_usdt": round(float(fees_usdt), 4),
            "hold_seg": round(float(duracion_seg), 2),
            "es_entrada_maker": bool(es_entrada_maker),
            "es_salida_maker": bool(es_salida_maker),
            "mfe_max_pnl_pct": round(float(mfe_pct) * 100.0, 4),
            "mae_min_pnl_pct": round(float(mae_pct) * 100.0, 4),
            "lvr_bps": lvr_trade,
        }
        if vector_entrada:
            registro["vector_entrada"] = dict(vector_entrada)
        if trayectoria_pnl:
            registro["trayectoria_pnl"] = dict(trayectoria_pnl)

        self.operaciones.append(registro)

        if persistir_disco and not cfg.es_modo_test():
            try:
                with open(self.ruta_ledger, mode="a", encoding="utf-8") as fh:
                    fh.write(json.dumps(registro, ensure_ascii=True) + "\n")
                ram.guardar_registro_baul_forense(
                    {
                        "tipo_evento": "CIERRE_OPERACION_REAL",
                        **registro,
                    }
                )
            except Exception:
                pass
        return registro

    def obtener_resumen(self) -> Dict[str, Any]:
        total = len(self.operaciones)
        wins = sum(1 for op in self.operaciones if float(op.get("pnl_usdt", 0.0)) > 0.0)
        losses = total - wins
        scratches = sum(
            1 for op in self.operaciones
            if op.get("es_scratch") or "SCRATCH" in str(op.get("motivo_salida", "")).upper()
        )
        pnl_total = round(sum(float(op.get("pnl_usdt", 0.0)) for op in self.operaciones), 4)
        win_rate = round((wins / total) * 100.0, 1) if total > 0 else 0.0
        best_pnl = max((float(op.get("pnl_usdt", 0.0)) for op in self.operaciones), default=0.0)
        worst_pnl = min((float(op.get("pnl_usdt", 0.0)) for op in self.operaciones), default=0.0)
        map_prom = (
            round(sum(float(op.get("map_usdt", 0.0)) for op in self.operaciones) / total, 2)
            if total > 0
            else 0.0
        )
        pnl_over_map = round(pnl_total / map_prom, 4) if map_prom > 0.0 else 0.0
        lvr_vals = [float(op.get("lvr_bps", 0.0)) for op in self.operaciones if float(op.get("lvr_bps", 0.0)) > 0.0]
        lvr_prom = round(sum(lvr_vals) / len(lvr_vals), 4) if lvr_vals else 0.0
        balance_contable = round(self.base_balance_usdt + pnl_total + self.ajuste_paridad_usdt, 4)
        real_uta = round(
            self.real_uta_balance_usdt if self.real_uta_balance_usdt > 0.0 else balance_contable,
            4,
        )

        return {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "scratches": scratches,
            "win_rate": win_rate,
            "total_pnl_usdt": pnl_total,
            "best_usdt": round(best_pnl, 4),
            "worst_usdt": round(worst_pnl, 4),
            "map_usdt": map_prom,
            "pnl_over_map": pnl_over_map,
            "lvr": lvr_prom,
            "balance_usdt": balance_contable,
            "base_usdt": round(self.base_balance_usdt, 2),
            "real_usdt": real_uta,
        }

    def formatear_panel_ascii(self) -> List[str]:
        return mpl.formatear_panel_ascii_resumen(self.obtener_resumen())

    def imprimir_panel(self, consola: bool = True) -> None:
        for linea in self.formatear_panel_ascii():
            ram.log_operativo(linea, consola=consola)


GESTOR_ESTADISTICAS = GestorEstadisticasHFT()


def registrar_operacion_cerrada(
    symbol: str,
    side: str,
    precio_entrada: float,
    precio_salida: float,
    contratos: float,
    pnl_usdt: float,
    pnl_pct: float,
    motivo_salida: str,
    duracion_seg: float,
    fees_usdt: float = 0.0,
    es_entrada_maker: bool = True,
    es_salida_maker: bool = True,
    mfe_pct: float = 0.0,
    mae_pct: float = 0.0,
    volatilidad_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    vector_entrada: Optional[Dict[str, Any]] = None,
    trayectoria_pnl: Optional[Dict[str, float]] = None,
    imprimir_caja: bool = True,
) -> Dict[str, Any]:
    reg = GESTOR_ESTADISTICAS.registrar_operacion(
        symbol=symbol,
        side=side,
        precio_entrada=precio_entrada,
        precio_salida=precio_salida,
        contratos=contratos,
        pnl_usdt=pnl_usdt,
        pnl_pct=pnl_pct,
        motivo_salida=motivo_salida,
        duracion_seg=duracion_seg,
        fees_usdt=fees_usdt,
        es_entrada_maker=es_entrada_maker,
        es_salida_maker=es_salida_maker,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        volatilidad_bv=volatilidad_bv,
        vector_entrada=vector_entrada,
        trayectoria_pnl=trayectoria_pnl,
    )
    if imprimir_caja:
        GESTOR_ESTADISTICAS.imprimir_panel()
    return reg


def imprimir_panel_caja_negra(consola: bool = True) -> None:
    GESTOR_ESTADISTICAS.imprimir_panel(consola=consola)


def obtener_resumen_caja_negra() -> Dict[str, Any]:
    return GESTOR_ESTADISTICAS.obtener_resumen()
