"""
Level 6B DAG: Pure Single-Ticket Moallemi-Wald SPRT Optimal Stopping Exit Governor,
Hyperbolic Convex MFE Ratchet kappa(MFE_t, V_L2), Tick-Quantized Net-of-Fee Zero-Loss
Floor (SCAR-LOCK-14), +0.11% Early Break-Even Shield with Anti-Taker Pullback Cushion,
18.0s Multi-Step Elastic Maker Scratch, Startup Orphan Reconciler, and Colorized Live
CLI HUD (verbot) for HFT Doctor Blythe Engine - Production Baseline Terpsichora V7.0.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import config_parametros as cfg
from apoyo import micro_hud_ansi_telegram as mht
from apoyo import micro_inspector_forense as mif
import core_estado_ram as ram
from defensiva import micro_decaimiento_chronos_sl as mdcs
from defensiva import micro_escape_reconciliador as mer
from defensiva import micro_evacuador_scratch as mes
import ejecutor_sniper as eje
import escudo_tricortex as tri
from ofensiva import micro_cresta_convexo_sprt as mcw
from ofensiva import micro_desarme_unwind_pasivo as mdup
from ofensiva import micro_escudo_diamante_fase2 as medf
from ofensiva import micro_impulso_runner as mir
from ofensiva import micro_motor_wald_exit as mmw
import stats_tracker as st
import telemetria_telegram as tel


def calcular_pendiente_recuperacion_delise(
    pnl_pct: float,
    mae_pct: float,
    edad_seg: float,
    trayectoria_pnl: Optional[Dict[str, float]] = None,
) -> float:
    return mes.calcular_pendiente_recuperacion_delise(
        pnl_pct=pnl_pct, mae_pct=mae_pct, edad_seg=edad_seg, trayectoria_pnl=trayectoria_pnl
    )


def calcular_piso_be_maker(
    precio_entrada: float,
    side: str,
    tick_size: float = 0.0001,
) -> float:
    return mmw.calcular_piso_cero_perdida(precio_entrada, side, tick_size=tick_size)


def calcular_kappa_convexo_wald(
    mfe_pct: float,
    vacio_l2_ratio: float = 1.0,
) -> float:
    try:
        return mcw.calcular_kappa_convexo_wald(mfe_pct, vacio_l2_ratio=vacio_l2_ratio)
    except TypeError:
        return mcw.calcular_kappa_convexo_wald(mfe_pct)


def calcular_lambda_wald_sprt(
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    edad_seg: float,
    lambda_prev: float = 0.0,
    vol_bv: float = cfg.VOLATILIDAD_BV_PISO_MIN,
    hurst: float = 0.42,
    direccion: str = "LONG",
    vacio_l2_ratio: float = 1.0,
) -> float:
    try:
        return mcw.calcular_lambda_wald_sprt(
            pnl_pct=pnl_pct,
            mfe_pct=mfe_pct,
            ofi_5s=ofi_5s,
            edad_seg=edad_seg,
            lambda_prev=lambda_prev,
            vol_bv=vol_bv,
            hurst=hurst,
            direccion=direccion,
            vacio_l2_ratio=vacio_l2_ratio,
        )
    except TypeError:
        return mcw.calcular_lambda_wald_sprt(
            pnl_pct=pnl_pct,
            mfe_pct=mfe_pct,
            ofi_5s=ofi_5s,
            edad_seg=edad_seg,
            lambda_prev=lambda_prev,
            vol_bv=vol_bv,
            hurst=hurst,
            direccion=direccion,
        )


def _es_error_posicion_cerrada_bybit(exc: Exception) -> bool:
    txt = str(exc).lower()
    return (
        "110017" in txt
        or "position is zero" in txt
        or "current position is zero" in txt
        or "can not set tp/sl" in txt
        or ("reduce-only" in txt and "zero" in txt)
    )


def _calcular_mfe_capture_seguro(pos: ram.PosicionActiva, precio_salida: float, pnl_bruto_pct: float) -> float:
    if hasattr(pos, "calcular_mfe_capture_regularizado"):
        return float(pos.calcular_mfe_capture_regularizado(precio_salida))
    mfe_b = max(0.0, float(pos.max_pnl_pct_alcanzado))
    mae_b = abs(float(pos.min_pnl_pct_alcanzado))
    if pnl_bruto_pct >= 0.0 or mfe_b >= 0.0008:
        return round(max(-1.50, min(1.50, pnl_bruto_pct / max(mfe_b, 0.0008))), 4)
    return round(max(-1.50, min(0.0, -abs(pnl_bruto_pct) / max(mae_b, 0.0010))), 4)


def _construir_vector_forense_cierre(
    pos: ram.PosicionActiva,
    precio_salida: float,
    pnl_bruto_pct: float,
) -> Dict[str, Any]:
    m_close = ram.ESTADO_GLOBAL.metricas_ticks.get(pos.symbol)
    vacio_out = round(float(getattr(m_close, "vacio_l2_ratio", 1.0) or 1.0), 3) if m_close is not None else 1.0
    mfe_cap = _calcular_mfe_capture_seguro(pos, precio_salida, pnl_bruto_pct)
    return {
        "z_entry": pos.z_entrada,
        "dp_pct": round(pos.dp_entrada_pct * 100.0, 4),
        "ema900_pct": round(pos.ema900_entrada_pct * 100.0, 4),
        "ofi_entry": pos.ofi_entrada,
        "hurst_entry": pos.hurst_entrada,
        "hawkes_entry": pos.hawkes_entrada,
        "lyapunov_entry": pos.lyapunov_entrada,
        "volatilidad_bv": pos.volatilidad_bv_entrada,
        "volatilidad_bv_raw": float(getattr(pos, "volatilidad_bv_raw_entrada", pos.volatilidad_bv_entrada)),
        "percentil_24h": pos.percentil_entrada,
        "irrev_lob": round(float(getattr(pos, "irrev_lob_entrada", 0.0) or 0.0), 4),
        "imb_l1": round(float(getattr(pos, "imb_l1_entrada", 0.0) or 0.0), 4),
        "cancel_net_l1": round(float(getattr(pos, "cancel_net_l1_entrada", 0.0) or 0.0), 4),
        "vacio_l2_entry": round(float(getattr(pos, "vacio_l2_entrada", 1.0) or 1.0), 3),
        "q_l1_ratio_entry": round(float(getattr(pos, "q_l1_ratio_entrada", 1.0) or 1.0), 4),
        "fpt_race_ratio": round(float(getattr(pos, "fpt_race_ratio", 0.0) or 0.0), 4),
        "pendiente_delise": round(float(getattr(pos, "pendiente_delise", 0.0) or 0.0), 6),
        "lambda_wald_exit": pos.lambda_wald,
        "repeg_salida_count": pos.repeg_salida_count,
        "mfe_capture_ratio": mfe_cap,
        "vacio_l2_ratio": vacio_out,
    }


class GestorPosicionesChronosTriz:
    """
    Pure Single-Ticket Moallemi-Wald Position Lifecycle & Convex Ratchet Governor (Terpsichora V7.0).
    """

    def __init__(self) -> None:
        self.cierres_maker: int = 0
        self.cierres_taker: int = 0
        self.cosechas_50_ejecutadas: int = 0

    async def _actualizar_sl_bybit(
        self,
        exchange: Any,
        pos: ram.PosicionActiva,
        nuevo_sl: float,
        tick_size: float = 0.0001,
    ) -> bool:
        if exchange is None or not hasattr(exchange, "set_trading_stop"):
            return False
        try:
            m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(pos.symbol)
            bid_l = m_live.bid if m_live is not None else 0.0
            ask_l = m_live.ask if m_live is not None else 0.0
            sl_seguro = mes.ajustar_geometria_sl_markprice(
                nuevo_sl, pos.direccion, bid_l, ask_l, tick_size, buffer_ticks=1.0
            )
            await exchange.set_trading_stop(
                pos.symbol,
                {"stopLoss": str(sl_seguro), "slTriggerBy": "MarkPrice"},
            )
            pos.sl_bybit = sl_seguro
            ram.log_operativo(f"[SNIPER] Bybit server SL on {pos.symbol} updated to {sl_seguro}")
            return True
        except Exception as exc:
            if _es_error_posicion_cerrada_bybit(exc):
                await self._procesar_cierre_externo_sl_exchange(pos)
            return False

    async def _procesar_cierre_externo_sl_exchange(
        self,
        pos: ram.PosicionActiva,
        precio_cierre_ref: Optional[float] = None,
    ) -> Dict[str, Any]:
        if pos.cerrada:
            return {}
        pos.cerrada = True
        ram.ESTADO_GLOBAL.posiciones_activas.pop(pos.symbol, None)
        px_out = float(precio_cierre_ref or pos.sl_bybit or pos.sl_interno or pos.precio_entrada)
        pnl_bruto_pct = pos.calcular_pnl_bruto_pct(px_out)
        nocional_out = abs(pos.contratos * px_out)
        fee_out = nocional_out * cfg.COMISION_TAKER_PCT
        fees_tot = pos.fees_acumulados_usdt + fee_out
        pnl_bruto_usdt = abs(pos.contratos * pos.precio_entrada) * pnl_bruto_pct
        pnl_neto_usdt = round(pos.pnl_realizado_parcial_usdt + pnl_bruto_usdt - fees_tot, 4)
        nocional_ini = max(1e-6, pos.nocional_entrada_usdt)
        pnl_neto_pct = pnl_neto_usdt / nocional_ini
        duracion = max(1.0, time.time() - pos.timestamp_apertura)
        self.cierres_taker += 1
        ram.log_operativo(
            f"[SNIPER] [LOSS] CLOSE {pos.symbol} [SL_EXCHANGE] "
            f"{pos.precio_entrada} -> {px_out} | {pnl_neto_pct * 100:+.2f} % "
            f"({pnl_neto_usdt:+.4f} USDT) in {int(duracion)}s"
        )
        vector_in = _construir_vector_forense_cierre(pos, px_out, pnl_bruto_pct)
        reg = st.registrar_operacion_cerrada(
            symbol=pos.symbol,
            side=pos.direccion,
            precio_entrada=pos.precio_entrada,
            precio_salida=px_out,
            contratos=pos.contratos_iniciales,
            pnl_usdt=pnl_neto_usdt,
            pnl_pct=pnl_neto_pct,
            motivo_salida="SL_EXCHANGE",
            duracion_seg=duracion,
            fees_usdt=fees_tot,
            es_entrada_maker=pos.es_entrada_maker,
            es_salida_maker=False,
            mfe_pct=pos.max_pnl_pct_alcanzado,
            mae_pct=pos.min_pnl_pct_alcanzado,
            volatilidad_bv=pos.volatilidad_bv_entrada,
            vector_entrada=vector_in,
            trayectoria_pnl=pos.trayectoria_pnl,
        )
        tel.notificar_cierre_confirmado(
            symbol=pos.symbol,
            side=pos.direccion,
            precio_entrada=pos.precio_entrada,
            precio_salida=px_out,
            pnl_pct=pnl_neto_pct,
            pnl_usdt=pnl_neto_usdt,
            motivo="SL_EXCHANGE",
            duracion_seg=duracion,
            balance_uta=st.GESTOR_ESTADISTICAS.obtener_resumen()["balance_usdt"],
        )
        await tri.ORQUESTADOR_TRICORTEX.ejecutar_forense_post_perdida(
            pos.symbol, "SL_EXCHANGE", pnl_neto_usdt
        )
        return reg

    async def _finalizar_cierre_posicion(
        self,
        pos: ram.PosicionActiva,
        precio_salida: float,
        motivo: str,
        es_maker: bool,
    ) -> Dict[str, Any]:
        if pos.cerrada:
            return {}
        pos.cerrada = True
        ram.ESTADO_GLOBAL.posiciones_activas.pop(pos.symbol, None)
        pnl_bruto_pct = pos.calcular_pnl_bruto_pct(precio_salida)
        pnl_bruto_usdt = abs(pos.contratos * pos.precio_entrada) * pnl_bruto_pct
        tasa_fee = cfg.COMISION_MAKER_PCT if es_maker else cfg.COMISION_TAKER_PCT
        fee_salida = abs(pos.contratos * precio_salida) * tasa_fee
        fees_totales = pos.fees_acumulados_usdt + fee_salida
        pnl_neto_usdt = round(pos.pnl_realizado_parcial_usdt + pnl_bruto_usdt - fees_totales, 4)
        nocional_ini = max(1e-6, pos.nocional_entrada_usdt)
        pnl_neto_pct = pnl_neto_usdt / nocional_ini
        duracion = max(1.0, time.time() - pos.timestamp_apertura)
        if es_maker:
            self.cierres_maker += 1
        else:
            self.cierres_taker += 1

        if pnl_neto_usdt > 0.0:
            etiqueta = "[WIN]"
            cd_win = float(cfg.obtener_aux("COOLDOWN_POST_CIERRE_GANADOR_SEG", 25.0))
            ram.ESTADO_GLOBAL.activar_cooldown_par(pos.symbol, cd_win, motivo="WIN_COOLDOWN")
        elif "SCRATCH" in motivo.upper():
            etiqueta = "[SCRATCH]"
            cd_seg = float(cfg.obtener_aux("COOLDOWN_MAKER_SCRATCH_18S", 75.0))
            ram.ESTADO_GLOBAL.activar_cooldown_par(pos.symbol, cd_seg, motivo="SCRATCH_COOLDOWN")
        else:
            etiqueta = "[LOSS]"

        if pos.direccion == "SHORT" and pnl_neto_usdt <= 0.0:
            perm = ram.ESTADO_GLOBAL.whitelist_pares.get(pos.symbol)
            if perm is not None:
                perm.step_lock_short_price = precio_salida
                perm.step_lock_short_until = time.time() + float(cfg.obtener_aux("STEP_LOCK_SHORT_SEG", 1800.0))

        side_str = "SHORT " if pos.direccion == "SHORT" else ""
        ram.log_operativo(
            f"[SNIPER] {etiqueta} CLOSE {side_str}{pos.symbol} [{motivo}] "
            f"{pos.precio_entrada} -> {precio_salida} | {pnl_neto_pct * 100:+.2f} % "
            f"({pnl_neto_usdt:+.4f} USDT) in {int(duracion)}s"
        )
        vector_in = _construir_vector_forense_cierre(pos, precio_salida, pnl_bruto_pct)
        reg = st.registrar_operacion_cerrada(
            symbol=pos.symbol,
            side=pos.direccion,
            precio_entrada=pos.precio_entrada,
            precio_salida=precio_salida,
            contratos=pos.contratos_iniciales,
            pnl_usdt=pnl_neto_usdt,
            pnl_pct=pnl_neto_pct,
            motivo_salida=motivo,
            duracion_seg=duracion,
            fees_usdt=fees_totales,
            es_entrada_maker=pos.es_entrada_maker,
            es_salida_maker=es_maker,
            mfe_pct=pos.max_pnl_pct_alcanzado,
            mae_pct=pos.min_pnl_pct_alcanzado,
            volatilidad_bv=pos.volatilidad_bv_entrada,
            vector_entrada=vector_in,
            trayectoria_pnl=pos.trayectoria_pnl,
        )
        tel.notificar_cierre_confirmado(
            symbol=pos.symbol,
            side=pos.direccion,
            precio_entrada=pos.precio_entrada,
            precio_salida=precio_salida,
            pnl_pct=pnl_neto_pct,
            pnl_usdt=pnl_neto_usdt,
            motivo=motivo,
            duracion_seg=duracion,
            balance_uta=st.GESTOR_ESTADISTICAS.obtener_resumen()["balance_usdt"],
        )
        if pnl_neto_usdt < 0.0 and "SCRATCH" not in motivo.upper():
            await tri.ORQUESTADOR_TRICORTEX.ejecutar_forense_post_perdida(
                pos.symbol, motivo, pnl_neto_usdt
            )
        return reg

    async def _ejecutar_cierre_taker(
        self,
        exchange: Any,
        pos: ram.PosicionActiva,
        precio_ref: float,
        motivo: str,
    ) -> Dict[str, Any]:
        if pos.cerrada:
            return {}
        side_close = "sell" if pos.direccion == "LONG" else "buy"
        if pos.orden_salida_id:
            try:
                await exchange.cancel_order(pos.orden_salida_id, pos.symbol)
            except Exception:
                pass
            pos.orden_salida_id = ""
            pos.en_proceso_cierre = False
        try:
            orden = await exchange.create_order(
                pos.symbol,
                "market",
                side_close,
                pos.contratos,
                None,
                {"reduceOnly": True},
            )
            px_out = float(orden.get("average") or orden.get("price") or 0.0)
            oid = str(orden.get("id", ""))
            if px_out <= 0.0 and oid and not cfg.es_modo_test() and hasattr(exchange, "fetch_order"):
                await asyncio.sleep(max(0.05, float(cfg.LATENCIA_ACK_BYBIT_MS) / 1000.0))
                try:
                    est_f = await eje.consultar_orden_segura(exchange, oid, pos.symbol, precio_ref)
                    px_out = float(est_f.get("average") or est_f.get("price") or precio_ref)
                except Exception:
                    px_out = precio_ref
            if px_out <= 0.0:
                px_out = precio_ref
            return await self._finalizar_cierre_posicion(pos, px_out, motivo, es_maker=False)
        except Exception as exc:
            if _es_error_posicion_cerrada_bybit(exc):
                return await self._procesar_cierre_externo_sl_exchange(pos, precio_ref)
            raise

    async def _ejecutar_cosecha_50_triz(
        self,
        exchange: Any,
        pos: ram.PosicionActiva,
        best_bid: float,
        best_ask: float,
        tick_size: float,
        step_size: float,
    ) -> bool:
        if pos.cosecha_50_ejecutada or pos.cerrada:
            return False
        lote_50 = eje.cuantizar_lote(pos.contratos * 0.50, step_size)
        if lote_50 <= 0.0 or (pos.contratos - lote_50) <= 0.0:
            return False
        side_close = "sell" if pos.direccion == "LONG" else "buy"
        px_harvest = best_ask if pos.direccion == "LONG" else best_bid
        px_harvest = eje.cuantizar_tick(px_harvest, tick_size)
        try:
            orden = await exchange.create_order(
                pos.symbol,
                "limit",
                side_close,
                lote_50,
                px_harvest,
                {"timeInForce": "PostOnly", "postOnly": True, "reduceOnly": True},
            )
            oid = str(orden.get("id", ""))
            st_ord = str(orden.get("status", "")).lower()
            filled = float(orden.get("filled", 0.0) or 0.0)
            if st_ord not in ("closed", "filled") and filled < lote_50 and oid:
                estado_f = await eje.consultar_orden_segura(exchange, oid, pos.symbol, px_harvest)
                filled = float(estado_f.get("filled", lote_50) or lote_50)
                px_harvest = float(estado_f.get("average") or estado_f.get("price") or px_harvest)
            if filled > 0.0:
                pnl_pct_tramo = pos.calcular_pnl_bruto_pct(px_harvest)
                bruto_tramo = abs(filled * pos.precio_entrada) * pnl_pct_tramo
                fee_tramo = abs(filled * px_harvest) * cfg.COMISION_MAKER_PCT
                neto_tramo = round(bruto_tramo - fee_tramo, 4)
                pos.contratos = round(max(0.0, pos.contratos - filled), 6)
                pos.pnl_realizado_parcial_usdt = round(pos.pnl_realizado_parcial_usdt + neto_tramo, 6)
                pos.fees_acumulados_usdt = round(pos.fees_acumulados_usdt + fee_tramo, 6)
                pos.cosecha_50_ejecutada = True
                self.cosechas_50_ejecutadas += 1
                ram.log_operativo(
                    f"[SNIPER] [DIAMOND] {pos.symbol} 50% TRIZ PostOnly Harvest executed: "
                    f"{filled} @ {px_harvest} ({pnl_pct_tramo * 100:+.2f}% | {neto_tramo:+.4f} USDT). "
                    f"{pos.contratos} contracts remaining in 50/25/25 Ladder."
                )
                tel.notificar_cosecha_parcial(pos.symbol, filled, px_harvest, pnl_pct_tramo, neto_tramo)
                return True
        except Exception as exc:
            if _es_error_posicion_cerrada_bybit(exc):
                await self._procesar_cierre_externo_sl_exchange(pos, px_harvest)
        return False

    async def _iniciar_o_actualizar_salida_maker(
        self,
        exchange: Any,
        pos: ram.PosicionActiva,
        best_bid: float,
        best_ask: float,
        tick_size: float,
        motivo: str,
        ahora: float,
        ofi_5s: float = 0.0,
        precio_objetivo_custom: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        if pos.cerrada:
            return None
        side_close = "sell" if pos.direccion == "LONG" else "buy"
        motivo_up = motivo.upper()
        m_exit = ram.ESTADO_GLOBAL.metricas_ticks.get(pos.symbol)
        vacio_exit = float(getattr(m_exit, "vacio_l2_ratio", 1.0) or 1.0) if m_exit is not None else 1.0
        edad_orden_act = (
            max(0.0, ahora - pos.ts_orden_salida)
            if (pos.en_proceso_cierre and pos.ts_orden_salida > 0.0)
            else 0.0
        )

        if "SCRATCH" in motivo_up:
            ofi_dir = ofi_5s if pos.direccion == "LONG" else -ofi_5s
            try:
                px_target = mes.calcular_precio_scratch_acotado_un_tick(
                    pos.direccion,
                    pos.precio_entrada,
                    best_bid,
                    best_ask,
                    tick_size,
                    ofi_dir,
                    edad_orden_salida_seg=edad_orden_act,
                    repeg_salida_count=pos.repeg_salida_count,
                    vacio_l2_ratio=vacio_exit,
                )
            except TypeError:
                px_target = mes.calcular_precio_scratch_acotado_un_tick(
                    pos.direccion, pos.precio_entrada, best_bid, best_ask, tick_size, ofi_dir
                )
            px_target = eje.cuantizar_tick(px_target, tick_size)
        elif precio_objetivo_custom > 0.0:
            px_punta = best_ask if pos.direccion == "LONG" else best_bid
            px_raw = max(px_punta, precio_objetivo_custom) if pos.direccion == "LONG" else min(px_punta, precio_objetivo_custom)
            px_target = eje.cuantizar_tick(px_raw, tick_size)
        else:
            px_target = best_ask if pos.direccion == "LONG" else best_bid
            px_target = eje.cuantizar_tick(px_target, tick_size)

        exige_piso_cero_perdida = (
            pos.trinquete_be_activo
            or "UNWIND" in motivo_up
            or "TRINQUETE_BE" in motivo_up
            or "TRAILING" in motivo_up
        ) and "SCRATCH" not in motivo_up
        if exige_piso_cero_perdida:
            piso_be = (
                pos.sl_interno
                if (pos.trinquete_be_activo and pos.sl_interno > 0.0)
                else calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
            )
            if "TRINQUETE_BE" in motivo_up and (
                pos.repeg_salida_count >= 1
                or edad_orden_act >= 4.5
                or (ahora - pos.timestamp_apertura) >= 55.0
            ):
                t_sz = max(1e-8, float(tick_size))
                banda_relax_pct = min(
                    0.00090,
                    0.00025 * max(1.0, float(pos.repeg_salida_count) + (edad_orden_act / 4.5)),
                )
                piso_relax = (
                    eje.cuantizar_tick(pos.precio_entrada * (1.0 - banda_relax_pct), t_sz, modo="floor")
                    if pos.direccion == "LONG"
                    else eje.cuantizar_tick(pos.precio_entrada * (1.0 + banda_relax_pct), t_sz, modo="ceil")
                )
                if pos.direccion == "LONG":
                    px_target = max(piso_relax, best_ask if best_ask > 0.0 else px_target)
                else:
                    px_target = min(piso_relax, best_bid if best_bid > 0.0 else px_target)
            else:
                if pos.direccion == "LONG" and px_target < piso_be:
                    px_target = piso_be
                elif pos.direccion == "SHORT" and px_target > piso_be:
                    px_target = piso_be

        if not pos.en_proceso_cierre or not pos.orden_salida_id:
            try:
                orden = await exchange.create_order(
                    pos.symbol,
                    "limit",
                    side_close,
                    pos.contratos,
                    px_target,
                    {"timeInForce": "PostOnly", "postOnly": True, "reduceOnly": True},
                )
                st_now = str(orden.get("status", "")).lower()
                filled_now = float(orden.get("filled", 0.0) or 0.0)
                if st_now in ("closed", "filled") or filled_now >= pos.contratos:
                    px_fill = float(orden.get("average") or orden.get("price") or px_target)
                    return await self._finalizar_cierre_posicion(pos, px_fill, motivo, es_maker=True)
                if st_now in ("canceled", "cancelled", "rejected", "expired"):
                    if filled_now > 0.0:
                        pos.contratos = round(max(0.0, pos.contratos - filled_now), 6)
                    pos.en_proceso_cierre = False
                    pos.orden_salida_id = ""
                    return None
                pos.en_proceso_cierre = True
                pos.orden_salida_id = str(orden.get("id", ""))
                pos.ts_orden_salida = ahora
                pos.ultimo_repeg_salida_ts = ahora
                pos.ultimo_poll_salida_ts = ahora
                pos.precio_orden_salida = px_target
                pos.motivo_salida_pendiente = motivo
                if cfg.es_modo_test():
                    est_f = await eje.consultar_orden_segura(exchange, pos.orden_salida_id, pos.symbol, px_target)
                    st_f = str(est_f.get("status", "")).lower()
                    if st_f in ("closed", "filled") or float(est_f.get("filled", 0.0) or 0.0) >= pos.contratos:
                        px_fill = float(est_f.get("average") or est_f.get("price") or px_target)
                        return await self._finalizar_cierre_posicion(pos, px_fill, motivo, es_maker=True)
            except Exception as exc:
                if _es_error_posicion_cerrada_bybit(exc):
                    return await self._procesar_cierre_externo_sl_exchange(pos, px_target)
            return None

        if not cfg.es_modo_test() and (ahora - pos.ultimo_poll_salida_ts) < 0.45:
            return None
        try:
            pos.ultimo_poll_salida_ts = ahora
            est_ord = await eje.consultar_orden_segura(exchange, pos.orden_salida_id, pos.symbol, pos.precio_orden_salida)
            st_ord = str(est_ord.get("status", "")).lower()
            filled_ord = float(est_ord.get("filled", 0.0) or 0.0)
            if st_ord in ("closed", "filled") or filled_ord >= pos.contratos:
                px_fill = float(est_ord.get("average") or est_ord.get("price") or pos.precio_orden_salida)
                return await self._finalizar_cierre_posicion(
                    pos, px_fill, pos.motivo_salida_pendiente or motivo, es_maker=True
                )
            if st_ord in ("canceled", "cancelled", "rejected", "expired"):
                if filled_ord > 0.0:
                    pos.contratos = round(max(0.0, pos.contratos - filled_ord), 6)
                pos.en_proceso_cierre = False
                pos.orden_salida_id = ""
                return None

            if "SCRATCH" in motivo_up:
                intervalo_repeg = 0.55 if (vacio_exit < 0.60 or pos.repeg_salida_count >= 2) else 0.75
            else:
                try:
                    intervalo_repeg = medf.calcular_intervalo_repeg_salida_maker(
                        motivo_up, repeg_salida_count=pos.repeg_salida_count, vacio_l2_ratio=vacio_exit
                    )
                except TypeError:
                    intervalo_repeg = medf.calcular_intervalo_repeg_salida_maker(motivo_up)

            urgencia_be = bool(
                pos.trinquete_be_activo
                and motivo == "TRINQUETE_BE_MAKER"
                and pos.motivo_salida_pendiente != "TRINQUETE_BE_MAKER"
            )
            if (urgencia_be or (ahora - pos.ultimo_repeg_salida_ts) >= intervalo_repeg) and px_target != pos.precio_orden_salida:
                params_exit_po = {"timeInForce": "PostOnly", "postOnly": True, "reduceOnly": True}
                accion_ex, nid_ex, ord_ex = await eje.enmendar_o_reemplazar_orden_maker(
                    exchange,
                    pos.orden_salida_id,
                    pos.symbol,
                    side_close,
                    pos.contratos,
                    px_target,
                    params_exit_po,
                    precio_anterior=pos.precio_orden_salida,
                )
                if accion_ex == "FILLED_IN_TRANSIT":
                    px_fill_tr = float(ord_ex.get("average") or ord_ex.get("price") or pos.precio_orden_salida)
                    return await self._finalizar_cierre_posicion(
                        pos, px_fill_tr, pos.motivo_salida_pendiente or motivo, es_maker=True
                    )
                pos.orden_salida_id = nid_ex
                pos.precio_orden_salida = px_target
                pos.motivo_salida_pendiente = motivo
                pos.ultimo_repeg_salida_ts = ahora
                pos.repeg_salida_count += 1
        except Exception as exc:
            if _es_error_posicion_cerrada_bybit(exc):
                return await self._procesar_cierre_externo_sl_exchange(pos, px_target)
        return None

    async def evaluar_posicion_activa(
        self,
        exchange: Any,
        pos: ram.PosicionActiva,
        precio_actual: float,
        best_bid: float,
        best_ask: float,
        ofi_5s: float = 0.0,
        tick_size: float = 0.0001,
        step_size: float = 0.1,
        ahora: Optional[float] = None,
        modo_escalera_50_50: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if pos.cerrada or precio_actual <= 0.0:
            return None
        ts_now = float(ahora) if ahora is not None else time.time()
        edad = ts_now - pos.timestamp_apertura
        _ = calcular_ajuste_elastico_posicion_en_vivo(pos, max(0.0, edad), ofi_5s, tick_size)
        pnl_pct = pos.actualizar_excursion(precio_actual, ts_now)
        ctrl = ram.ESTADO_GLOBAL.controlador_autonomo
        m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(pos.symbol)
        h_live = m_live.hurst if m_live is not None else pos.hurst_entrada
        vacio_rat_l2 = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0) if m_live is not None else 1.0
        ofi_dir_live = ofi_5s if pos.direccion == "LONG" else -ofi_5s

        if hasattr(pos, "pendiente_delise"):
            pos.pendiente_delise = calcular_pendiente_recuperacion_delise(
                pnl_pct, pos.min_pnl_pct_alcanzado, edad, trayectoria_pnl=pos.trayectoria_pnl
            )

        pos.lambda_wald = calcular_lambda_wald_sprt(
            pnl_pct=pnl_pct,
            mfe_pct=pos.max_pnl_pct_alcanzado,
            ofi_5s=ofi_5s,
            edad_seg=edad,
            lambda_prev=pos.lambda_wald,
            vol_bv=pos.volatilidad_bv_entrada,
            hurst=h_live,
            direccion=pos.direccion,
            vacio_l2_ratio=vacio_rat_l2,
        )
        lambda_w = pos.lambda_wald

        try:
            forzar_90s, activar_pre_escape_72s, motivo_esc = mer.evaluar_escape_temporal_posicion(
                edad,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                pos.direccion,
                pos.en_proceso_cierre,
                lambda_wald=lambda_w,
                vacio_l2_ratio=vacio_rat_l2,
            )
        except TypeError:
            forzar_90s, activar_pre_escape_72s, motivo_esc = mer.evaluar_escape_temporal_posicion(
                edad, pnl_pct, pos.max_pnl_pct_alcanzado, ofi_5s, pos.direccion, pos.en_proceso_cierre
            )
        if forzar_90s:
            ram.log_operativo(
                f"[SNIPER] {pos.symbol} reached maximum hold time "
                f"({int(edad)}s >= {int(cfg.TIEMPO_MAX_HOLD_SEG)}s). Liquidating position to release margin."
            )
            return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, motivo_esc)

        try:
            pos.sl_interno = mdcs.calcular_sl_interno_chronos(
                pos.precio_entrada,
                pos.direccion,
                pos.sl_interno,
                edad,
                pos.max_pnl_pct_alcanzado,
                tick_size,
                pos.trinquete_be_activo,
                lambda_wald=lambda_w,
                vacio_l2_ratio=vacio_rat_l2,
            )
        except TypeError:
            pos.sl_interno = mdcs.calcular_sl_interno_chronos(
                pos.precio_entrada,
                pos.direccion,
                pos.sl_interno,
                edad,
                pos.max_pnl_pct_alcanzado,
                tick_size,
                pos.trinquete_be_activo,
            )
        be_hit, sl_be_efectivo = medf.verificar_disparo_fisico_trinquete_be(
            pos.direccion,
            pos.trinquete_be_activo,
            pos.sl_interno,
            pos.precio_entrada,
            precio_actual,
            be_offset_pct=float(cfg.TRINQUETE_BE_OFFSET_PCT),
        )
        if pos.trinquete_be_activo and sl_be_efectivo > 0.0:
            pos.sl_interno = sl_be_efectivo

        sl_hit = (
            be_hit
            or (pos.direccion == "LONG" and precio_actual <= pos.sl_interno)
            or (pos.direccion == "SHORT" and precio_actual >= pos.sl_interno)
        )
        if sl_hit:
            if pos.trinquete_be_activo:
                try:
                    absorber_be = mmw.debe_absorber_micro_retroceso_be_temprano(
                        pos.direccion,
                        edad,
                        pnl_pct,
                        pos.max_pnl_pct_alcanzado,
                        ofi_5s,
                        lambda_w,
                        pos.trailing_activo,
                        pos.symbol,
                        vacio_l2_ratio=vacio_rat_l2,
                    )
                except TypeError:
                    absorber_be = mmw.debe_absorber_micro_retroceso_be_temprano(
                        pos.direccion,
                        edad,
                        pnl_pct,
                        pos.max_pnl_pct_alcanzado,
                        ofi_5s,
                        lambda_w,
                        pos.trailing_activo,
                        pos.symbol,
                    )
                if absorber_be:
                    return None
                res_be = await self._iniciar_o_actualizar_salida_maker(
                    exchange, pos, best_bid, best_ask, tick_size, "TRINQUETE_BE_MAKER", ts_now, ofi_5s=ofi_5s
                )
                if res_be is not None:
                    return res_be
                edad_orden_be = max(0.0, ts_now - pos.ts_orden_salida) if pos.ts_orden_salida > 0.0 else 0.0
                ruptura_profunda_be = (
                    pnl_pct <= -0.0011
                    or (
                        edad_orden_be >= 4.0
                        and pnl_pct <= -0.00085
                        and (ofi_dir_live <= -0.18 or vacio_rat_l2 < 0.55 or pos.repeg_salida_count >= 2)
                    )
                )
                if not ruptura_profunda_be:
                    return None
                return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, "TRINQUETE_BE_MAKER")
            return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, "SL_INTERNO_CHRONOS")

        umbral_cosecha = float(ctrl.get("w3_tp_maker_pct", cfg.COSECHA_TRIZ_ACTIVACION_PCT))
        umbral_stall = float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT))

        # 1. Early Break-Even Shield at +0.11% MFE
        if pos.max_pnl_pct_alcanzado >= umbral_stall and not pos.trinquete_be_activo and pnl_pct < umbral_cosecha:
            piso_be_early = calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
            pos.sl_interno = piso_be_early
            pos.trinquete_be_activo = True
            ram.log_operativo(
                f"[SNIPER] [SHIELD] {pos.symbol} Early Break-Even Ratchet armed at MFE "
                f"{pos.max_pnl_pct_alcanzado * 100:+.2f}%: SL {piso_be_early}"
            )
            await self._actualizar_sl_bybit(exchange, pos, piso_be_early, tick_size=tick_size)

        # 2. Pure Single-Ticket Moallemi-Wald Convex Ratchet (or 50/50 Ladder when modo_escalera_50_50=True)
        if pos.max_pnl_pct_alcanzado >= umbral_cosecha:
            piso_be = calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
            kappa = calcular_kappa_convexo_wald(pos.max_pnl_pct_alcanzado, vacio_l2_ratio=vacio_rat_l2)
            if pos.direccion == "LONG":
                piso_convexo = eje.cuantizar_tick(
                    pos.precio_entrada * (1.0 + (kappa * pos.max_pnl_pct_alcanzado)),
                    tick_size,
                    modo="floor",
                )
                nuevo_piso = max(piso_be, piso_convexo)
                mejoro_piso = nuevo_piso > pos.sl_interno
            else:
                piso_convexo = eje.cuantizar_tick(
                    pos.precio_entrada * (1.0 - (kappa * pos.max_pnl_pct_alcanzado)),
                    tick_size,
                    modo="ceil",
                )
                nuevo_piso = min(piso_be, piso_convexo)
                mejoro_piso = (pos.sl_interno <= 0.0) or (nuevo_piso < pos.sl_interno)

            primera_activacion_wald = not pos.trailing_activo
            if primera_activacion_wald or mejoro_piso:
                pos.sl_interno = nuevo_piso
                pos.trinquete_be_activo = True
            if modo_escalera_50_50 and not pos.cosecha_50_ejecutada:
                await self._ejecutar_cosecha_50_triz(
                    exchange, pos, best_bid, best_ask, tick_size, step_size
                )
                return None
            if primera_activacion_wald:
                pos.trailing_activo = True
                ram.log_operativo(
                    f"[SNIPER] [SHIELD] {pos.symbol} Single-Ticket Wald Convex Ratchet armed (100% lot): "
                    f"Zero-Loss Floor {pos.sl_interno} (PnL {pnl_pct * 100:+.2f}%, "
                    f"MFE {pos.max_pnl_pct_alcanzado * 100:+.2f}%, kappa={kappa:.2f}, Lambda={lambda_w:+.2f})"
                )
                await self._actualizar_sl_bybit(exchange, pos, pos.sl_interno, tick_size=tick_size)
            if pos.max_pnl_pct_alcanzado >= 0.0042 and pnl_pct >= 0.0042:
                ram.log_operativo(f"[SNIPER] {pos.symbol} Trailing Stop activated (PnL {pnl_pct * 100:+.2f}%)")
            flujo_agotado_cresta = mcw.evaluar_agotamiento_cresta_wald(
                pos.max_pnl_pct_alcanzado, pnl_pct, ofi_5s, edad, lambda_w, kappa, pos.direccion
            )
            if flujo_agotado_cresta:
                pos.cosecha_activa = True
                pos.motivo_salida_pendiente = "TRAILING_RATCHET_MAKER"
                ram.log_operativo(
                    f"[WALD-SPRT CREST] {pos.symbol} 100% Single-Ticket exit on flow exhaustion @ "
                    f"{best_ask if pos.direccion == 'LONG' else best_bid} "
                    f"(PnL {pnl_pct * 100:+.2f}%, MFE {pos.max_pnl_pct_alcanzado * 100:+.2f}%, "
                    f"kappa={kappa:.2f}, Lambda={lambda_w:+.2f})"
                )
                return await self._iniciar_o_actualizar_salida_maker(
                    exchange, pos, best_bid, best_ask, tick_size, "TRAILING_RATCHET_MAKER", ts_now, ofi_5s=ofi_5s
                )

        # 3. Phase 2 Stall Harvest & [DIAMOND] Phase 2 Maker Shield PostOnly (16s+) with L2 Wall/Vacuum Intelligence
        muro_op_l2 = (
            (m_live.muro_ask_px if pos.direccion == "LONG" else m_live.muro_bid_px)
            if m_live is not None
            else 0.0
        )
        diamante_ok, px_diamante = medf.evaluar_activacion_escudo_diamante_fase2(
            pos.direccion, pos.precio_entrada, precio_actual, best_bid, best_ask,
            edad, pnl_pct, lambda_w, tick_size, fase2_ya_ejecutada=pos.cosecha_activa,
            muro_opuesto_px=muro_op_l2, vacio_l2_ratio=vacio_rat_l2,
        )
        try:
            stall_ok = mdup.evaluar_cosecha_estancamiento_mfe(
                pos.direccion,
                edad,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                umbral_stall,
                vacio_l2_ratio=vacio_rat_l2,
                lambda_wald=lambda_w,
            )
            unwind_42_ok = mdup.evaluar_desarme_maker_unwind_42s(
                pos.direccion,
                edad,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                pos.cosecha_activa,
                symbol=pos.symbol,
                vacio_l2_ratio=vacio_rat_l2,
                lambda_wald=lambda_w,
            )
        except TypeError:
            stall_ok = mdup.evaluar_cosecha_estancamiento_mfe(
                pos.direccion, edad, pnl_pct, pos.max_pnl_pct_alcanzado, ofi_5s, umbral_stall
            )
            unwind_42_ok = mdup.evaluar_desarme_maker_unwind_42s(
                pos.direccion, edad, pnl_pct, pos.max_pnl_pct_alcanzado, ofi_5s, pos.cosecha_activa
            )
        try:
            inhibir_rally = mmw.debe_inhibir_maker_unwind_en_rally(
                pos.direccion,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                pos.symbol,
                vacio_l2_ratio=vacio_rat_l2,
                lambda_wald=lambda_w,
            )
        except TypeError:
            inhibir_rally = mmw.debe_inhibir_maker_unwind_en_rally(
                pos.direccion,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                pos.symbol,
                vacio_l2_ratio=vacio_rat_l2,
            )

        if (
            (
                diamante_ok
                or stall_ok
                or unwind_42_ok
                or (edad >= 16.0 and pnl_pct >= umbral_stall and (lambda_w <= 0.15 or ofi_dir_live <= 0.08))
            )
            and (not inhibir_rally)
        ):
            if not pos.trinquete_be_activo and pnl_pct >= (float(cfg.TRINQUETE_BE_OFFSET_PCT) + 0.00025):
                piso_be = calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
                pos.sl_interno = piso_be
                pos.trinquete_be_activo = True
                await self._actualizar_sl_bybit(exchange, pos, piso_be, tick_size=tick_size)
            pos.cosecha_activa = True
            pos.motivo_salida_pendiente = "MAKER_UNWIND"
            px_cot_f2 = px_diamante if (diamante_ok and px_diamante > 0.0) else (best_ask if pos.direccion == "LONG" else best_bid)
            if not pos.en_proceso_cierre:
                ram.log_operativo(
                    f"[SNIPER] [DIAMOND] {pos.symbol} Phase 2 Maker Shield PostOnly executed @ "
                    f"{px_cot_f2} "
                    f"(PnL {pnl_pct * 100:+.2f}%, Lambda={lambda_w:+.2f}, age {int(edad)}s)"
                )
            return await self._iniciar_o_actualizar_salida_maker(
                exchange, pos, best_bid, best_ask, tick_size, "MAKER_UNWIND", ts_now,
                ofi_5s=ofi_5s, precio_objetivo_custom=(px_diamante if diamante_ok else 0.0)
            )

        if (
            pos.en_proceso_cierre
            and pos.orden_salida_id
            and "SCRATCH" in str(pos.motivo_salida_pendiente).upper()
            and pnl_pct >= (float(cfg.COMISION_MAKER_PCT) * 2.2)
            and ofi_dir_live >= 0.12
            and lambda_w >= 0.25
        ):
            try:
                await exchange.cancel_order(pos.orden_salida_id, pos.symbol)
            except Exception:
                pass
            pos.en_proceso_cierre = False
            pos.orden_salida_id = ""
            pos.motivo_salida_pendiente = ""
            pos.repeg_salida_count = 0

        # === [KEEP-ALIVE-ACTIVE-MAKER-EXIT] ===
        if pos.orden_salida_id and not pos.cerrada:
            _motivo_act = (
                pos.motivo_salida_pendiente
                or ("MAKER_SCRATCH_18S" if pos.max_pnl_pct_alcanzado <= 0.0008 else "MAKER_UNWIND")
            )
            res_keepalive = await self._iniciar_o_actualizar_salida_maker(
                exchange, pos, best_bid, best_ask, tick_size, _motivo_act, ts_now, ofi_5s=ofi_5s
            )
            if res_keepalive is not None:
                return res_keepalive

        # 4. Pre-Escape Passive Evacuation at 54s-72s
        if activar_pre_escape_72s:
            motivo_72s = (
                "MAKER_UNWIND"
                if (pos.trinquete_be_activo or pnl_pct >= cfg.TRINQUETE_BE_OFFSET_PCT)
                else "MAKER_SCRATCH_18S"
            )
            if not pos.en_proceso_cierre:
                ram.log_operativo(
                    f"[PHANTOM PRE-ESCAPE P-05] {pos.symbol} passive PostOnly evacuation ({motivo_72s}) "
                    f"at {edad:.1f}s @ {best_ask if pos.direccion == 'LONG' else best_bid} "
                    f"(PnL {pnl_pct * 100:+.2f}%, Lambda={lambda_w:+.2f})."
                )
            return await self._iniciar_o_actualizar_salida_maker(
                exchange, pos, best_bid, best_ask, tick_size, motivo_72s, ts_now, ofi_5s=ofi_5s
            )

        # 5. Law 2 (RF-18): 18.0s Passive Maker-Scratch on Dead Fills (Delegated to defensiva/)
        hurst_live = m_live.hurst if m_live is not None else pos.hurst_entrada
        acel_live = m_live.aceleracion_lyapunov if m_live is not None else pos.lyapunov_entrada
        acel_dir_live = acel_live if pos.direccion == "LONG" else -acel_live
        try:
            ventana_28s_ok = mes.evaluar_ventana_elastica_scratch_28s(
                edad,
                pos.max_pnl_pct_alcanzado,
                pnl_pct,
                ofi_dir_live,
                acel_lyap_dir=acel_dir_live,
                vacio_l2_ratio=vacio_rat_l2,
            )
            wald_scratch_ready = ventana_28s_ok and mes.evaluar_gatillo_maker_scratch_18s(
                pos.direccion,
                edad,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                lambda_w,
                pos.trinquete_be_activo,
                hurst_actual=hurst_live,
                fill_post_aborto=False,
                mae_pct=pos.min_pnl_pct_alcanzado,
                trayectoria_pnl=pos.trayectoria_pnl,
                vacio_l2_ratio=vacio_rat_l2,
            )
            escalar_sc_tk = pos.en_proceso_cierre and mes.debe_escalar_scratch_colgado_a_taker(
                pos.direccion,
                max(0.0, ts_now - pos.ts_orden_salida),
                pnl_pct,
                ofi_5s,
                pos.motivo_salida_pendiente,
                repeg_salida_count=pos.repeg_salida_count,
                vacio_l2_ratio=vacio_rat_l2,
            )
        except TypeError:
            ventana_28s_ok = mes.evaluar_ventana_elastica_scratch_28s(
                edad, pos.max_pnl_pct_alcanzado, pnl_pct, ofi_dir_live, acel_lyap_dir=acel_dir_live
            )
            wald_scratch_ready = ventana_28s_ok and mes.evaluar_gatillo_maker_scratch_18s(
                pos.direccion,
                edad,
                pnl_pct,
                pos.max_pnl_pct_alcanzado,
                ofi_5s,
                lambda_w,
                pos.trinquete_be_activo,
                hurst_actual=hurst_live,
                fill_post_aborto=False,
                mae_pct=pos.min_pnl_pct_alcanzado,
                trayectoria_pnl=pos.trayectoria_pnl,
            )
            escalar_sc_tk = pos.en_proceso_cierre and mes.debe_escalar_scratch_colgado_a_taker(
                pos.direccion,
                max(0.0, ts_now - pos.ts_orden_salida),
                pnl_pct,
                ofi_5s,
                pos.motivo_salida_pendiente,
            )

        if escalar_sc_tk:
            return await self._ejecutar_cierre_taker(
                exchange, pos, precio_actual, "MAKER_SCRATCH_18S"
            )
        if wald_scratch_ready:
            if not pos.en_proceso_cierre:
                ram.log_operativo(
                    f"[MAKER-SCRATCH 18s] {pos.symbol} no rebound after {edad:.1f}s "
                    f"(PnL {pnl_pct * 100:+.2f}%, MFE {pos.max_pnl_pct_alcanzado * 100:+.2f}%, OFI5s {ofi_5s:+.2f}): "
                    f"evacuating via Limit PostOnly @ {best_ask if pos.direccion == 'LONG' else best_bid}."
                )
            return await self._iniciar_o_actualizar_salida_maker(
                exchange, pos, best_bid, best_ask, tick_size, "MAKER_SCRATCH_18S", ts_now, ofi_5s=ofi_5s
            )
        try:
            forzar_sc_est = pos.en_proceso_cierre and mir.debe_forzar_evacuacion_scratch_estancado(
                pos.en_proceso_cierre,
                pos.motivo_salida_pendiente,
                ts_now - pos.ts_orden_salida,
                pnl_pct,
                ofi_5s,
                pos.direccion,
                repeg_salida_count=pos.repeg_salida_count,
                vacio_l2_ratio=vacio_rat_l2,
            )
        except TypeError:
            forzar_sc_est = pos.en_proceso_cierre and mir.debe_forzar_evacuacion_scratch_estancado(
                pos.en_proceso_cierre,
                pos.motivo_salida_pendiente,
                ts_now - pos.ts_orden_salida,
                pnl_pct,
                ofi_5s,
                pos.direccion,
            )
        if forzar_sc_est:
            ram.log_operativo(
                f"[MAKER-SCRATCH ESCALATION] {pos.symbol} passive scratch unfilled after "
                f"{ts_now - pos.ts_orden_salida:.1f}s with PnL {pnl_pct * 100:+.2f}%: "
                f"evacuating immediately to prevent full SL hit."
            )
            return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, "MAKER_SCRATCH_18S")

        if pos.cosecha_activa or (pos.en_proceso_cierre and pos.orden_salida_id):
            return await self._iniciar_o_actualizar_salida_maker(
                exchange,
                pos,
                best_bid,
                best_ask,
                tick_size,
                pos.motivo_salida_pendiente or "TRAILING_RATCHET_MAKER",
                ts_now,
                ofi_5s=ofi_5s,
            )
        return None


async def reconciliar_posiciones_huerfanas_arranque(exchange: Any) -> int:
    if exchange is None or not hasattr(exchange, "fetch_positions"):
        return 0
    procesadas = 0
    try:
        posiciones = await exchange.fetch_positions()
        ahora_s = time.time()
        ahora_ms = ahora_s * 1000.0
        for p in posiciones or []:
            contratos = abs(float(p.get("contracts") or p.get("size") or 0.0))
            if contratos <= 0.0:
                continue
            symbol = str(p.get("symbol", ""))
            side_raw = str(p.get("side", "long")).lower()
            entry_px = float(p.get("entryPrice") or p.get("avgPrice") or 0.0)
            mark_px = float(p.get("markPrice") or entry_px)
            if symbol in ram.ESTADO_GLOBAL.posiciones_activas:
                continue
            info_p = p.get("info") if isinstance(p.get("info"), dict) else {}
            ts_ms = float(
                info_p.get("updatedTime")
                or info_p.get("uTime")
                or p.get("updatedTime")
                or p.get("timestamp")
                or (ahora_ms - 240000.0)
            )
            raw_age = max(0.0, (ahora_ms - ts_ms) / 1000.0)
            en_gracia = mer.debe_adoptar_en_lugar_de_liquidar_huerfana(
                symbol,
                ram.ESTADO_GLOBAL.locks_pre_fill,
                ram.ESTADO_GLOBAL.posiciones_activas,
                ahora_s,
                grace_seg=5.0,
            )
            if (en_gracia or 0.0 < raw_age < 75.0) and len(ram.ESTADO_GLOBAL.posiciones_activas) < cfg.SLOTS_CONCURRENTES_MAX:
                dir_ad = "LONG" if side_raw in ("long", "buy") else "SHORT"
                sl_int_a, sl_srv_a = eje.calcular_niveles_sl_iniciales(entry_px, dir_ad, 0.0001)
                pos_ad = ram.PosicionActiva(
                    symbol=symbol,
                    side=dir_ad,
                    contratos=contratos,
                    contratos_iniciales=contratos,
                    precio_entrada=entry_px,
                    timestamp_apertura=ahora_s - min(raw_age, 74.0),
                    sl_interno=sl_int_a,
                    sl_bybit=sl_srv_a,
                    fees_acumulados_usdt=round(abs(contratos * entry_px) * cfg.COMISION_MAKER_PCT, 6),
                    es_entrada_maker=True,
                )
                ram.ESTADO_GLOBAL.posiciones_activas[symbol] = pos_ad
                await GESTOR_POSICIONES._actualizar_sl_bybit(exchange, pos_ad, sl_srv_a, tick_size=0.0001)
                ram.log_operativo(
                    f"[RECONCILER] [ORPHAN-SHIELD] Fresh UTA position on {symbol} (age {raw_age:.1f}s < 75s) "
                    f"adopted into active Wald custody: {contratos} @ {entry_px} (SL {sl_int_a})."
                )
                continue
            edad_seg = 300.0 if raw_age > 86400.0 else max(95.0, raw_age)
            edad_min = edad_seg / 60.0
            ram.log_operativo(
                f"[RECONCILER] Zombie orphan position detected on {symbol}: "
                f"{contratos} contracts @ {entry_px} (age {edad_min:.1f} min >= 90s). "
                f"Liquidating at market to release margin..."
            )
            side_close = "sell" if side_raw in ("long", "buy") else "buy"
            orden = await exchange.create_order(
                symbol,
                "market",
                side_close,
                contratos,
                None,
                {"reduceOnly": True},
            )
            px_out = float(orden.get("average") or orden.get("price") or mark_px)
            info_h = mer.clasificar_posicion_huerfana_arranque(
                symbol, side_raw, contratos, entry_px, px_out
            )
            pnl_bruto_pct = float(info_h["pnl_bruto_pct"])
            nocional = contratos * entry_px
            fee_est = (contratos * px_out) * cfg.COMISION_TAKER_PCT
            pnl_neto_usdt = round((nocional * pnl_bruto_pct) - fee_est, 4)
            pnl_neto_pct = pnl_neto_usdt / max(1e-6, nocional)
            etiqueta = "[WIN]" if pnl_neto_usdt > 0.0 else "[LOSS]"
            ram.log_operativo(
                f"[SNIPER] {etiqueta} CLOSE {symbol} [ESCAPE_HUERFANA_BOOT] "
                f"{entry_px} -> {px_out} | {pnl_neto_pct * 100:+.2f} % "
                f"({pnl_neto_usdt:+.4f} USDT) in {int(edad_seg)}s"
            )
            st.registrar_operacion_cerrada(
                symbol=symbol,
                side="LONG" if side_raw in ("long", "buy") else "SHORT",
                precio_entrada=entry_px,
                precio_salida=px_out,
                contratos=contratos,
                pnl_usdt=pnl_neto_usdt,
                pnl_pct=pnl_neto_pct,
                motivo_salida="ESCAPE_HUERFANA_BOOT",
                duracion_seg=edad_seg,
                fees_usdt=fee_est,
                es_entrada_maker=False,
                es_salida_maker=False,
            )
            procesadas += 1
        if procesadas > 0:
            ram.log_operativo(
                f"[RECONCILER] Startup reconciliation completed: {procesadas} position(s) processed."
            )
        else:
            if hasattr(exchange, "cancel_all_orders"):
                for _sym_c in cfg.PARES_CAMPEONES:
                    if _sym_c in ram.ESTADO_GLOBAL.posiciones_activas:
                        continue
                    try:
                        await exchange.cancel_all_orders(_sym_c)
                    except Exception:
                        pass
            ram.log_operativo("[RECONCILER] No orphan positions open on Bybit. Open orders swept & margin 100% clear.")
    except Exception as exc:
        ram.log_operativo(f"[RECONCILER] Warning during startup scan: {exc}")
    return procesadas


def colorear_linea_log_mobaxterm(linea: str) -> str:
    return mht.colorear_linea_log_mobaxterm(linea)


def imprimir_hud_verbot_cli(lineas_log: int = 18) -> None:
    mht.imprimir_hud_verbot_cli(lineas_log=lineas_log)


def seguir_log_en_vivo_cli(lineas_iniciales: int = 16) -> None:
    mht.seguir_log_en_vivo_cli(lineas_iniciales=lineas_iniciales)


def imprimir_radiografia_uta_cli() -> None:
    mht.imprimir_hud_verbot_cli(lineas_log=12)


def imprimir_auditoria_forense_cli() -> None:
    mif.imprimir_auditoria_forense_cli()


GESTOR_POSICIONES = GestorPosicionesChronosTriz()
def calcular_ajuste_elastico_posicion_en_vivo(
    pos: Any,
    edad_seg: float,
    ofi_actual: float,
    tick_size: float,
) -> Dict[str, float]:
    """Enlaza Zero-Giveaway Elastic Scratch y el Trinquete Convexo de Wald en gestor_posiciones.py."""
    from defensiva import micro_evacuador_scratch as _mes
    from ofensiva import micro_motor_wald_exit as _mmwe
    es_long = str(getattr(pos, "side", "LONG")).upper() in ("BUY", "LONG")
    ofi_dir = float(ofi_actual) if es_long else -float(ofi_actual)
    mfe_pct = float(getattr(pos, "mfe_max_pnl_pct", 0.0) or 0.0)
    ticks_giveaway = _mes.calcular_concesion_ticks_scratch_elastica(
        edad_posicion_seg=float(edad_seg),
        delta_t_orden_salida=max(0.0, float(edad_seg) - 18.0),
        ofi_dir=ofi_dir,
        mfe_alcanzado_pct=mfe_pct / 100.0,
    )
    piso_convexo = _mmwe.calcular_ratchet_convexo_mfe_elastico(
        precio_entrada=float(getattr(pos, "entry_price", 0.0) or 0.0),
        mfe_pct=mfe_pct,
        v_l2=float(getattr(pos, "vacio_l2_entrada", 1.0) or 1.0),
        eta_mfe_hist=0.50,
        es_long=es_long,
        tick_size=float(tick_size),
    )
    return {
        "ticks_scratch_giveaway": float(ticks_giveaway),
        "piso_wald_convexo": float(piso_convexo),
    }
