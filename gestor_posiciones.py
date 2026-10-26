"""
Level 6B DAG: Abraham Wald SPRT Optimal Stopping Exit Governor, Tick-Quantized
Net-of-Fee Zero-Loss Floor (SCAR-LOCK-14), Terpsichora Active Maker Chase
50/50 & 100% Harvest Ratchet, 100% Maker Scratch Custody, Startup Orphan
Reconciler, and Live CLI HUD (verbot) for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import config_parametros as cfg
import core_estado_ram as ram
import ejecutor_sniper as eje
import escudo_tricortex as tri
import stats_tracker as st
import telemetria_telegram as tel


def calcular_piso_be_maker(
    precio_entrada: float,
    side: str,
    tick_size: float = 0.0001,
) -> float:
    """
    SCAR-LOCK-14: Tick-Quantized Net-of-Fee Zero-Loss Floor.
    Guarantees strictly positive net PnL after round-trip Maker/Taker fees.
    """
    offset_min = max(
        float(cfg.TRINQUETE_BE_OFFSET_PCT),
        (cfg.COMISION_MAKER_PCT + cfg.COMISION_TAKER_PCT) * 1.15,
    )
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
    if dir_norm == "LONG":
        raw = precio_entrada * (1.0 + offset_min)
        piso = eje.cuantizar_tick(raw, tick_size, modo="ceil")
        if piso <= precio_entrada:
            piso = round(precio_entrada + max(tick_size, 1e-6), 6)
        return piso

    raw = precio_entrada * (1.0 - offset_min)
    techo = eje.cuantizar_tick(raw, tick_size, modo="floor")
    if techo >= precio_entrada:
        techo = round(precio_entrada - max(tick_size, 1e-6), 6)
    return techo


def calcular_lambda_wald_sprt(
    pnl_pct: float,
    mfe_pct: float,
    ofi_5s: float,
    edad_seg: float,
) -> float:
    impulso_pnl = (pnl_pct - 0.0004) * 950.0
    impulso_ofi = ofi_5s * 3.8
    decaimiento_tiempo = max(0.0, (edad_seg - 15.0) * 0.065)
    retroceso_mfe = max(0.0, (mfe_pct - pnl_pct) * 650.0)
    val = impulso_pnl + impulso_ofi - decaimiento_tiempo - retroceso_mfe
    return round(max(-4.00, min(4.00, val)), 2)


def _es_error_posicion_cerrada_bybit(exc: Exception) -> bool:
    txt = str(exc).lower()
    return (
        "110017" in txt
        or "position is zero" in txt
        or "current position is zero" in txt
        or "can not set tp/sl" in txt
        or ("reduce-only" in txt and "zero" in txt)
    )


class GestorPosicionesChronosTriz:
    """
    Terpsichora V1.0 Position Lifecycle & Active Maker Harvest Governor.
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
            t_size = max(1e-8, float(tick_size))
            sl_seguro = float(nuevo_sl)
            m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(pos.symbol)
            if m_live is not None and m_live.bid > 0.0 and m_live.ask > 0.0:
                if pos.direccion == "LONG" and sl_seguro >= m_live.bid:
                    sl_seguro = eje.cuantizar_tick(m_live.bid - t_size, t_size, modo="floor")
                elif pos.direccion == "SHORT" and sl_seguro <= m_live.ask:
                    sl_seguro = eje.cuantizar_tick(m_live.ask + t_size, t_size, modo="ceil")

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
            cd_seg = float(cfg.obtener_aux("COOLDOWN_POST_CIERRE_GANADOR_SEG", 25.0))
            ram.ESTADO_GLOBAL.activar_cooldown_par(pos.symbol, cd_seg, motivo="WIN_COOLDOWN")
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

        vector_in = {
            "z_entry": pos.z_entrada,
            "dp_pct": round(pos.dp_entrada_pct * 100.0, 4),
            "ema900_pct": round(pos.ema900_entrada_pct * 100.0, 4),
            "ofi_entry": pos.ofi_entrada,
            "hurst_entry": pos.hurst_entrada,
            "hawkes_entry": pos.hawkes_entrada,
            "lyapunov_entry": pos.lyapunov_entrada,
            "volatilidad_bv": pos.volatilidad_bv_entrada,
            "percentil_24h": pos.percentil_entrada,
        }

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
                    est_f = await exchange.fetch_order(oid, pos.symbol)
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
                estado_f = await exchange.fetch_order(oid, pos.symbol)
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
    ) -> Optional[Dict[str, Any]]:
        if pos.cerrada:
            return None

        side_close = "sell" if pos.direccion == "LONG" else "buy"
        px_target = best_ask if pos.direccion == "LONG" else best_bid
        px_target = eje.cuantizar_tick(px_target, tick_size)

        motivo_up = motivo.upper()
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
                    est_f = await exchange.fetch_order(pos.orden_salida_id, pos.symbol)
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
            est_ord = await exchange.fetch_order(pos.orden_salida_id, pos.symbol)
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

            intervalo_repeg = (
                cfg.COSECHA_REPEG_INTERVALO_SEG
                if ("UNWIND" in motivo_up or "HARVEST" in motivo_up or "TRAILING" in motivo_up)
                else 1.80
            )
            if (ahora - pos.ultimo_repeg_salida_ts) >= intervalo_repeg and px_target != pos.precio_orden_salida:
                await exchange.cancel_order(pos.orden_salida_id, pos.symbol)
                nueva = await exchange.create_order(
                    pos.symbol,
                    "limit",
                    side_close,
                    pos.contratos,
                    px_target,
                    {"timeInForce": "PostOnly", "postOnly": True, "reduceOnly": True},
                )
                pos.orden_salida_id = str(nueva.get("id", pos.orden_salida_id))
                pos.precio_orden_salida = px_target
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
        pnl_pct = pos.actualizar_excursion(precio_actual, ts_now)
        ctrl = ram.ESTADO_GLOBAL.controlador_autonomo

        if edad >= cfg.TIEMPO_MAX_HOLD_SEG:
            ram.log_operativo(
                f"[SNIPER] {pos.symbol} reached maximum hold time "
                f"({int(edad)}s >= {int(cfg.TIEMPO_MAX_HOLD_SEG)}s). Liquidating position to release margin."
            )
            return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, "ESCAPE_TEMPORAL")

        sl_hit = (
            (pos.direccion == "LONG" and precio_actual <= pos.sl_interno)
            or (pos.direccion == "SHORT" and precio_actual >= pos.sl_interno)
        )
        if sl_hit:
            if pos.trinquete_be_activo:
                res_be = await self._iniciar_o_actualizar_salida_maker(
                    exchange, pos, best_bid, best_ask, tick_size, "TRINQUETE_BE_MAKER", ts_now
                )
                if res_be is not None or pnl_pct > -0.0008:
                    return res_be
                return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, "TRINQUETE_BE_MAKER")
            return await self._ejecutar_cierre_taker(exchange, pos, precio_actual, "SL_INTERNO_CHRONOS")

        umbral_cosecha = float(ctrl.get("w3_tp_maker_pct", cfg.COSECHA_TRIZ_ACTIVACION_PCT))
        umbral_stall = float(ctrl.get("mfe_stall_harvest_pct", cfg.COSECHA_ESTANCAMIENTO_MFE_PCT))

        if pos.max_pnl_pct_alcanzado >= umbral_stall and not pos.trinquete_be_activo and pnl_pct < umbral_cosecha:
            piso_be_early = calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
            pos.sl_interno = piso_be_early
            pos.trinquete_be_activo = True
            ram.log_operativo(
                f"[SNIPER] [SHIELD] {pos.symbol} Early Break-Even Ratchet armed at MFE "
                f"{pos.max_pnl_pct_alcanzado * 100:+.2f}%: SL {piso_be_early}"
            )
            await self._actualizar_sl_bybit(exchange, pos, piso_be_early, tick_size=tick_size)

        if pnl_pct >= umbral_cosecha and not pos.cosecha_activa and not pos.cosecha_50_ejecutada:
            if not pos.trinquete_be_activo:
                piso_be = calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
                pos.sl_interno = piso_be
                pos.trinquete_be_activo = True
                ram.log_operativo(
                    f"[SNIPER] [SHIELD] {pos.symbol} Break-Even Ratchet armed: "
                    f"SL {piso_be} (PnL {pnl_pct * 100:+.2f}%)"
                )
                sl_srv_be = (
                    eje.cuantizar_tick(
                        pos.precio_entrada * (1.0 + float(cfg.obtener_aux("TRINQUETE_BE_BYBIT_OFFSET_PCT", 0.00060))),
                        tick_size,
                        modo="ceil",
                    )
                    if pos.direccion == "LONG"
                    else eje.cuantizar_tick(
                        pos.precio_entrada * (1.0 - float(cfg.obtener_aux("TRINQUETE_BE_BYBIT_OFFSET_PCT", 0.00060))),
                        tick_size,
                        modo="floor",
                    )
                )
                await self._actualizar_sl_bybit(exchange, pos, sl_srv_be, tick_size=tick_size)

            if modo_escalera_50_50 or cfg.COSECHA_TRIZ_FRACCION_LOTE < 0.99:
                await self._ejecutar_cosecha_50_triz(
                    exchange, pos, best_bid, best_ask, tick_size, step_size
                )
                return None
            else:
                pos.cosecha_activa = True
                pos.motivo_salida_pendiente = "MAKER_UNWIND"
                ram.log_operativo(
                    f"[SNIPER] [DIAMOND] {pos.symbol} Full-Maker Harvest 100% PostOnly executed @ "
                    f"{best_ask if pos.direccion == 'LONG' else best_bid} "
                    f"(PnL {pnl_pct * 100:+.2f}%, OFI={ofi_5s:+.2f}, age {int(edad)}s)"
                )
                return await self._iniciar_o_actualizar_salida_maker(
                    exchange, pos, best_bid, best_ask, tick_size, "MAKER_UNWIND", ts_now
                )

        if pos.trinquete_be_activo and pnl_pct >= 0.0042:
            if not pos.trailing_activo:
                pos.trailing_activo = True
                ram.log_operativo(f"[SNIPER] {pos.symbol} Trailing Stop activated (PnL {pnl_pct * 100:+.2f}%)")
            p_trail = (
                eje.cuantizar_tick(pos.precio_entrada * (1.0 + (pos.max_pnl_pct_alcanzado * 0.65)), tick_size)
                if pos.direccion == "LONG"
                else eje.cuantizar_tick(pos.precio_entrada * (1.0 - (pos.max_pnl_pct_alcanzado * 0.65)), tick_size)
            )
            if (pos.direccion == "LONG" and p_trail > pos.sl_interno) or (
                pos.direccion == "SHORT" and p_trail < pos.sl_interno
            ):
                pos.sl_interno = p_trail
            if pnl_pct <= (pos.max_pnl_pct_alcanzado * 0.72) or ofi_5s <= -0.10:
                return await self._iniciar_o_actualizar_salida_maker(
                    exchange, pos, best_bid, best_ask, tick_size, "TRAILING_RATCHET_MAKER", ts_now
                )

        lambda_w = calcular_lambda_wald_sprt(pnl_pct, pos.max_pnl_pct_alcanzado, ofi_5s, edad)
        if edad >= 16.0 and pnl_pct >= umbral_stall and (lambda_w <= 0.15 or ofi_5s <= 0.08):
            if not pos.trinquete_be_activo:
                piso_be = calcular_piso_be_maker(pos.precio_entrada, pos.direccion, tick_size)
                pos.sl_interno = piso_be
                pos.trinquete_be_activo = True
                await self._actualizar_sl_bybit(exchange, pos, piso_be, tick_size=tick_size)
            pos.cosecha_activa = True
            pos.motivo_salida_pendiente = "MAKER_UNWIND"
            if not pos.en_proceso_cierre:
                ram.log_operativo(
                    f"[SNIPER] [DIAMOND] {pos.symbol} Phase 2 Maker Shield PostOnly executed @ "
                    f"{best_ask if pos.direccion == 'LONG' else best_bid} "
                    f"(PnL {pnl_pct * 100:+.2f}%, Lambda={lambda_w:+.2f}, age {int(edad)}s)"
                )
            return await self._iniciar_o_actualizar_salida_maker(
                exchange, pos, best_bid, best_ask, tick_size, "MAKER_UNWIND", ts_now
            )

        if edad >= float(cfg.obtener_aux("PRE_ESCAPE_MAKER_SEG", 72.0)):
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
                exchange, pos, best_bid, best_ask, tick_size, motivo_72s, ts_now
            )

        t_scratch = float(cfg.obtener_aux("MAKER_SCRATCH_TIEMPO_SEG", 18.0))
        ofi_adv = float(cfg.obtener_aux("MAKER_SCRATCH_OFI_ADVERSO", -0.15))
        flujo_contra = (
            (pos.direccion == "LONG" and ofi_5s <= ofi_adv)
            or (pos.direccion == "SHORT" and ofi_5s >= abs(ofi_adv))
        )
        sin_rebote_18s = (
            edad >= 18.0
            and not pos.trinquete_be_activo
            and pos.max_pnl_pct_alcanzado <= 0.00015
            and pnl_pct <= -0.0007
        )
        wald_scratch_ready = (
            (edad >= 18.0 and pnl_pct <= 0.0 and flujo_contra)
            or sin_rebote_18s
            or (edad >= t_scratch and pnl_pct <= -0.0006 and lambda_w <= -1.20)
        )
        if wald_scratch_ready:
            if not pos.en_proceso_cierre:
                ram.log_operativo(
                    f"[MAKER-SCRATCH 18s] {pos.symbol} no rebound after {edad:.1f}s "
                    f"(PnL {pnl_pct * 100:+.2f}%, MFE {pos.max_pnl_pct_alcanzado * 100:+.2f}%, OFI5s {ofi_5s:+.2f}): "
                    f"evacuating via Limit PostOnly @ {best_ask if pos.direccion == 'LONG' else best_bid}."
                )
            return await self._iniciar_o_actualizar_salida_maker(
                exchange, pos, best_bid, best_ask, tick_size, "MAKER_SCRATCH_18S", ts_now
            )

        if pos.cosecha_activa or (pos.en_proceso_cierre and pos.orden_salida_id):
            return await self._iniciar_o_actualizar_salida_maker(
                exchange,
                pos,
                best_bid,
                best_ask,
                tick_size,
                pos.motivo_salida_pendiente or "MAKER_UNWIND",
                ts_now,
            )

        return None


async def reconciliar_posiciones_huerfanas_arranque(exchange: Any) -> int:
    if exchange is None or not hasattr(exchange, "fetch_positions"):
        return 0
    procesadas = 0
    try:
        posiciones = await exchange.fetch_positions()
        ahora_ms = time.time() * 1000.0
        for p in posiciones or []:
            contratos = abs(float(p.get("contracts") or p.get("size") or 0.0))
            if contratos <= 0.0:
                continue
            symbol = str(p.get("symbol", ""))
            side_raw = str(p.get("side", "long")).lower()
            entry_px = float(p.get("entryPrice") or p.get("avgPrice") or 0.0)
            mark_px = float(p.get("markPrice") or entry_px)
            ts_ms = float(p.get("timestamp") or p.get("updatedTime") or (ahora_ms - 240000.0))
            edad_seg = max(95.0, (ahora_ms - ts_ms) / 1000.0)
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
            if side_raw in ("long", "buy"):
                pnl_bruto_pct = (px_out - entry_px) / entry_px if entry_px > 0.0 else 0.0
            else:
                pnl_bruto_pct = (entry_px - px_out) / entry_px if entry_px > 0.0 else 0.0

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
            ram.log_operativo("[RECONCILER] No orphan positions open on Bybit. Margin 100% clear.")
    except Exception as exc:
        ram.log_operativo(f"[RECONCILER] Warning during startup scan: {exc}")
    return procesadas

# ==============================================================================
# ANSI COLORIZER FOR LIVE CLI HUD (verbot) ? ZERO DISK CONTAMINATION
# ==============================================================================
_ANSI_RESET: str = "\033[0m"
_ANSI_BOLD_GREEN: str = "\033[1;92m"
_ANSI_BOLD_RED: str = "\033[1;91m"
_ANSI_BOLD_YELLOW: str = "\033[1;93m"
_ANSI_BOLD_CYAN: str = "\033[1;96m"
_ANSI_BOLD_MAGENTA: str = "\033[1;95m"
_ANSI_BOLD_WHITE: str = "\033[1;97m"
_ANSI_DIM_CYAN: str = "\033[0;36m"
_ANSI_DIM_GRAY: str = "\033[0;37m"


def colorear_linea_log_mobaxterm(linea: str) -> str:
    s = linea.rstrip("\r\n")
    if not s:
        return ""

    # 1. Wins, Approvals, Active Fills & Ready States -> Bright Green
    if (
        "[WIN]" in s
        or "[TARGET] Active" in s
        or "RAM SHIELD O(1): APPROVED" in s
        or "[READY TO FIRE]" in s
        or "[TELEGRAM] Startup notification" in s
    ):
        return f"{_ANSI_BOLD_GREEN}{s}{_ANSI_RESET}"

    # 2. Losses, Stop-Losses, Circuit Breakers & Errors -> Bright Red
    if (
        "[LOSS]" in s
        or "SL_INTERNO_CHRONOS" in s
        or "SL_EXCHANGE" in s
        or "[CIRCUIT BREAKER" in s
        or "VETO_TOXIC" in s
        or "ANTI_LUNA" in s
        or "Stream error" in s
        or "[ERROR]" in s
    ):
        return f"{_ANSI_BOLD_RED}{s}{_ANSI_RESET}"

    # 3. Harvests, Break-Even Ratchets, Trailing & Passive Re-Pegs -> Bright Cyan
    if (
        "[DIAMOND]" in s
        or "[SHIELD]" in s
        or "Break-Even Ratchet" in s
        or "Trailing Stop" in s
        or "Bybit server SL" in s
        or "[PASSIVE ALIGN" in s
    ):
        return f"{_ANSI_BOLD_CYAN}{s}{_ANSI_RESET}"

    # 4. Radar Triggers & Order Shots -> Bright Magenta
    if (
        "[RADAR]" in s
        or "[SNIPER] Order " in s
        or "[SHORT-SNIPER] Order " in s
    ):
        return f"{_ANSI_BOLD_MAGENTA}{s}{_ANSI_RESET}"

    # 5. Scratches, Queue Aborts, Unfilled Releases & Warnings -> Bright Yellow
    if (
        "[SCRATCH]" in s
        or "[MAKER-SCRATCH" in s
        or "[EARLY QUEUE ABORT]" in s
        or "[MIN FILL GUARD]" in s
        or "[PHANTOM" in s
        or "unfilled after" in s
        or "[WARN]" in s
        or "quarantine" in s
    ):
        return f"{_ANSI_BOLD_YELLOW}{s}{_ANSI_RESET}"

    # 6. Black Box Panel Lines inside Log -> Cyan / Dynamic PnL
    if "+===" in s or "|  [BLACK BOX]" in s or "|  MAP:" in s or "|  Balance:" in s:
        return f"{_ANSI_BOLD_CYAN}{s}{_ANSI_RESET}"
    if "|  Total PnL:" in s:
        color_pnl = _ANSI_BOLD_RED if "Total PnL: -" in s else _ANSI_BOLD_GREEN
        return f"{color_pnl}{s}{_ANSI_RESET}"

    # 7. Background LPU / Hot-Reload / Parity Sync -> Soft Cyan/Gray
    if (
        "[TRI-CORTEX" in s
        or "[HOT-RELOAD OOS]" in s
        or "[BLACK BOX 1:1]" in s
        or "[RECONCILER]" in s
        or "[QUANTUM OOS EVALUATOR]" in s
    ):
        return f"{_ANSI_DIM_CYAN}{s}{_ANSI_RESET}"

    return f"{_ANSI_DIM_GRAY}{s}{_ANSI_RESET}"


def imprimir_hud_verbot_cli(lineas_log: int = 18) -> None:
    st.GESTOR_ESTADISTICAS.cargar_historial_disco()
    res = st.GESTOR_ESTADISTICAS.obtener_resumen()
    color_pnl = _ANSI_BOLD_GREEN if res["total_pnl_usdt"] >= 0.0 else _ANSI_BOLD_RED

    print(f"{_ANSI_BOLD_CYAN}{'=' * 82}{_ANSI_RESET}")
    print(f"{_ANSI_BOLD_WHITE} {cfg.NOMBRE_ESTRATEGIA}{_ANSI_RESET}")
    print(f"{_ANSI_BOLD_CYAN}{'=' * 82}{_ANSI_RESET}")
    for l_box in st.GESTOR_ESTADISTICAS.formatear_panel_ascii():
        if "Total PnL:" in l_box:
            print(f" {color_pnl}{l_box}{_ANSI_RESET}")
        elif "[BLACK BOX]" in l_box:
            print(f" {_ANSI_BOLD_WHITE}{l_box}{_ANSI_RESET}")
        else:
            print(f" {_ANSI_BOLD_CYAN}{l_box}{_ANSI_RESET}")
    print(f"{_ANSI_DIM_CYAN}{'-' * 82}{_ANSI_RESET}")
    print(
        f" {_ANSI_BOLD_GREEN}[WIN/FILL]{_ANSI_RESET} | "
        f"{_ANSI_BOLD_CYAN}[BE/HARVEST/RE-PEG]{_ANSI_RESET} | "
        f"{_ANSI_BOLD_MAGENTA}[RADAR/ORDER]{_ANSI_RESET} | "
        f"{_ANSI_BOLD_YELLOW}[SCRATCH/TTL]{_ANSI_RESET} | "
        f"{_ANSI_BOLD_RED}[LOSS/SL/VETO]{_ANSI_RESET}"
    )
    print(f"{_ANSI_DIM_CYAN}{'-' * 82}{_ANSI_RESET}")
    ruta_log = cfg.obtener_ruta_archivo("ARCHIVO_LOG")
    if ruta_log.exists():
        ultimas = ruta_log.read_text(encoding="utf-8", errors="replace").splitlines()[-lineas_log:]
        for ln in ultimas:
            print(colorear_linea_log_mobaxterm(ln))
    else:
        print(f" {_ANSI_BOLD_YELLOW}[INFO] bot_hft.log not yet created.{_ANSI_RESET}")
    print(f"{_ANSI_BOLD_CYAN}{'=' * 82}{_ANSI_RESET}")


def imprimir_radiografia_uta_cli() -> None:
    imprimir_hud_verbot_cli(lineas_log=12)


GESTOR_POSICIONES = GestorPosicionesChronosTriz()
