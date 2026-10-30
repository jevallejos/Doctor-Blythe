"""
Level 6A DAG: Pure Moallemi-Stoikov Passive Maker (Limit PostOnly) Execution
Engine with Zero-RTT Micro-Price Pre-Lead (0ms), 250ms Queue-Jump Re-Peg,
First-Passage-Time Race Ratio Tracking (arXiv:2403.02572v2), Uncensored 16-Attribute
OPSR Telemetry (COLT 2026), Minimum Fill Guard (<15%), and Pre-Validated Bybit V5
MarkPrice Stop-Loss Geometry (SEI-02) for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V7.0.
"""
from __future__ import annotations
from defensiva.micro_escape_reconciliador import debe_adoptar_en_lugar_de_liquidar_huerfana
from ofensiva.micro_motor_maker import debe_proteger_orden_en_cola_por_flujo_favorable

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

import config_parametros as cfg
from ofensiva import micro_cotizador_stoikov as mcs
from ofensiva import micro_motor_maker as mmm
from ofensiva import micro_sizing_kelly as msk
from ofensiva import micro_retenedor_fill_parcial as mrfp
from defensiva import micro_evacuador_scratch as mes
import core_estado_ram as ram
import escudo_tricortex as tri
import radar_volatilidad as rad
import telemetria_telegram as tel


def cuantizar_tick(precio: float, tick_size: float, modo: str = "nearest") -> float:
    return mcs.cuantizar_tick(precio, tick_size, modo=modo)


def cuantizar_lote(cantidad: float, step_size: float) -> float:
    return mcs.cuantizar_lote(cantidad, step_size)


def calcular_precio_penny_jump(
    best_bid: float,
    best_ask: float,
    tick_size: float,
    side: str,
    micro_price: float = 0.0,
) -> float:
    return mcs.calcular_precio_penny_jump(best_bid, best_ask, tick_size, side, micro_price=micro_price)


def calcular_niveles_sl_iniciales(
    precio_entrada: float,
    side: str,
    tick_size: float = 0.0001,
) -> Tuple[float, float]:
    return mes.calcular_niveles_sl_iniciales(precio_entrada, side, tick_size=tick_size)


async def consultar_orden_segura(
    exchange: Any,
    orden_id: str,
    symbol: str,
    precio_fallback: float = 0.0,
) -> Dict[str, Any]:
    """
    CCXT Bybit V5 Safe Order Poller:
    Passes {"acknowledged": True} required by CCXT 4.5.x fetchOrder() on Bybit,
    falls back cleanly to 2-arg call on test mocks, and prevents loop crash
    on transient network/indexing delays.
    """
    try:
        return await exchange.fetch_order(orden_id, symbol, {"acknowledged": True})
    except TypeError:
        return await exchange.fetch_order(orden_id, symbol)
    except Exception as exc:
        if "acknowledged" in str(exc).lower():
            try:
                return await exchange.fetch_order(orden_id, symbol, {"acknowledged": True})
            except Exception:
                pass
        return {"id": orden_id, "status": "open", "filled": 0.0, "price": precio_fallback}


async def enmendar_o_reemplazar_orden_maker(
    exchange: Any,
    orden_id: str,
    symbol: str,
    side_ccxt: str,
    contratos: float,
    nuevo_px: float,
    params_post_only: Dict[str, Any],
    precio_anterior: float = 0.0,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Ejecuta enmienda atomica Bybit UTA V5 (/v5/order/amend via exchange.edit_order)
    en 1 solo RTT conservando prioridad y reserva de margen.
    Si el exchange o mock no soporta edit_order o la orden requiere reemplazo,
    ejecuta fallback seguro con verificacion de fill en transito.
    Retorna (estado_accion, nuevo_orden_id, dict_orden).
    """
    if hasattr(exchange, "edit_order"):
        try:
            editada = await exchange.edit_order(
                orden_id,
                symbol,
                "limit",
                side_ccxt,
                contratos,
                nuevo_px,
                params_post_only,
            )
            nuevo_id = str(editada.get("id") or orden_id)
            return "AMENDED", nuevo_id, editada
        except Exception as exc_ed:
            txt_e = str(exc_ed).lower()
            if any(k in txt_e for k in ("110001", "170213", "110017", "filled", "closed", "not exists", "too late")):
                if not cfg.es_modo_test():
                    est_chk = await consultar_orden_segura(exchange, orden_id, symbol, precio_anterior or nuevo_px)
                    st_c = str(est_chk.get("status", "")).lower()
                    if st_c in ("closed", "filled") or float(est_chk.get("filled", 0.0) or 0.0) > 0.0:
                        return "FILLED_IN_TRANSIT", orden_id, est_chk

    try:
        await exchange.cancel_order(orden_id, symbol)
    except Exception:
        pass
    if not cfg.es_modo_test():
        est_pre = await consultar_orden_segura(exchange, orden_id, symbol, precio_anterior or nuevo_px)
        if float(est_pre.get("filled", 0.0) or 0.0) > 0.0 or str(est_pre.get("status", "")).lower() in ("closed", "filled"):
            return "FILLED_IN_TRANSIT", orden_id, est_pre

    nueva_orden = await exchange.create_order(
        symbol,
        "limit",
        side_ccxt,
        contratos,
        nuevo_px,
        params_post_only,
    )
    nuevo_id = str(nueva_orden.get("id") or orden_id)
    return "REPLACED", nuevo_id, nueva_orden


class EjecutorSniperBybit:
    """
    Moallemi-Stoikov Zero-Adverse-Selection PostOnly Execution Engine (Terpsichora V7.0).
    """

    def __init__(self) -> None:
        self.disparos_intentados: int = 0
        self.disparos_llenados: int = 0
        self.disparos_repeg_ejecutados: int = 0
        self.disparos_abortados_cola: int = 0

    async def _colocar_sl_servidor_bybit(
        self,
        exchange: Any,
        symbol: str,
        sl_precio: float,
        side: str = "LONG",
        tick_size: float = 0.0001,
    ) -> bool:
        if exchange is None or not hasattr(exchange, "set_trading_stop"):
            return False
        try:
            dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
            m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
            bid_l = m_live.bid if m_live is not None else 0.0
            ask_l = m_live.ask if m_live is not None else 0.0
            sl_seguro = mes.ajustar_geometria_sl_markprice(
                sl_precio, dir_norm, bid_l, ask_l, tick_size, buffer_ticks=2.0
            )

            await exchange.set_trading_stop(
                symbol,
                {"stopLoss": str(sl_seguro), "slTriggerBy": "MarkPrice"},
            )
            return True
        except Exception:
            return False

    async def _refrescar_punta_libro_en_cola(self, exchange: Any, symbol: str) -> None:
        if cfg.es_modo_test() or exchange is None or not hasattr(exchange, "fetch_order_book"):
            return
        try:
            ob = await exchange.fetch_order_book(symbol, limit=10)
            rad.RADAR_GLOBAL.procesar_instantanea_libro(symbol, ob, time.time())
        except Exception:
            pass

    async def ejecutar_disparo_maker(
        self,
        exchange: Any,
        symbol: str,
        side: str,
        senal: Dict[str, Any],
        tick_size: float = 0.0001,
        step_size: float = 0.1,
        ttl_override: Optional[float] = None,
    ) -> Optional[ram.PosicionActiva]:
        dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
        side_ccxt = "buy" if dir_norm == "LONG" else "sell"
        etiqueta_log = "[SNIPER]" if dir_norm == "LONG" else "[SHORT-SNIPER]"

        if not ram.ESTADO_GLOBAL.tiene_capacidad_slot(dir_norm):
            return None

        if not ram.ESTADO_GLOBAL.adquirir_lock_pre_fill(symbol, ttl_seg=8.0):
            return None

        orden_id: str = ""
        pos: Optional[ram.PosicionActiva] = None
        try:
            best_bid = float(senal.get("bid") or senal.get("precio_ref") or 0.0)
            best_ask = float(senal.get("ask") or senal.get("precio_ref") or 0.0)
            micro_px = float(senal.get("micro_price") or 0.0)
            if best_bid <= 0.0 or best_ask <= 0.0:
                return None

            m_snap = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
            q_l1_init = float(
                senal.get("bid_qty" if dir_norm == "LONG" else "ask_qty")
                or (m_snap.bid_qty if (m_snap and dir_norm == "LONG") else (m_snap.ask_qty if m_snap else 0.0))
                or 100.0
            )
            q_opp_init = float(
                senal.get("ask_qty" if dir_norm == "LONG" else "bid_qty")
                or (m_snap.ask_qty if (m_snap and dir_norm == "LONG") else (m_snap.bid_qty if m_snap else 0.0))
                or 100.0
            )

            precio_inicial = calcular_precio_penny_jump(
                best_bid, best_ask, tick_size, dir_norm, micro_price=micro_px
            )
            precio_orden = precio_inicial
            z_val = float(senal.get("z_score", 0.0))
            ofi_val = float(senal.get("ofi", 0.0))
            hurst_val = float(senal.get("hurst", 0.42))

            kelly_frac, _, nocional_usdt = msk.calcular_dimension_kelly_uta(
                tri,
                capital_libre_usdt=msk.resolver_capital_base_uta(ram.ESTADO_GLOBAL.free_usdt),
                z_score=z_val,
                ofi=ofi_val,
                hurst=hurst_val,
                side=dir_norm,
                symbol=symbol,
            )
            if nocional_usdt < cfg.ORDEN_MINIMA_BYBIT_USDT:
                nocional_usdt = cfg.ORDEN_MINIMA_BYBIT_USDT

            contratos = cuantizar_lote(nocional_usdt / precio_orden, step_size)
            if contratos <= 0.0:
                return None

            nocional_real = round(contratos * precio_orden, 2)
            t0_net = time.perf_counter()
            params_post_only = {"timeInForce": "PostOnly", "postOnly": True}
            orden = await exchange.create_order(
                symbol,
                "limit",
                side_ccxt,
                contratos,
                precio_orden,
                params_post_only,
            )
            rtt_ms = (time.perf_counter() - t0_net) * 1000.0
            self.disparos_intentados += 1

            orden_id = str(orden.get("id", ""))
            ram.log_operativo(
                f"{etiqueta_log} Order {orden_id} on {symbol}: {contratos} @ {precio_orden} "
                f"(notional ~{nocional_real:.2f} USDT, {cfg.APALANCAMIENTO_OPERATIVO}x, "
                f"Kelly={kelly_frac * 100:.0f}%, Z={z_val:+.2f}, OFI={ofi_val:+.2f}, RTT={rtt_ms:.1f}ms)"
            )

            ttl_max = float(ttl_override) if ttl_override is not None else float(cfg.TTL_ORDEN_ENTRADA_SEG)
            permitir_repeg = (
                bool(cfg.PERMITIR_REQUOTE_ENTRADA)
                and ttl_override is None
                and ttl_max >= 1.50
            )
            repegs_hechos = 0
            ultimo_repeg_elapsed = 0.0
            abortada_en_cola = False
            q_l1_ratio_last = 1.0
            fpt_race_ratio_last = 0.0
            ts_inicio = time.perf_counter()
            paso_poll = min(0.08, max(0.02, ttl_max / 10.0))

            estado_orden = orden
            ttl_efectivo = ttl_max
            while (time.perf_counter() - ts_inicio) < ttl_efectivo:
                status_actual = str(estado_orden.get("status", "")).lower()
                filled_actual = float(estado_orden.get("filled", 0.0) or 0.0)
                if status_actual in ("closed", "filled") or filled_actual >= contratos:
                    break

                fue_cancelada_postonly = status_actual in ("canceled", "cancelled", "rejected", "expired")
                if fue_cancelada_postonly and (not permitir_repeg or repegs_hechos >= 2 or filled_actual > 0.0):
                    break

                if not fue_cancelada_postonly:
                    await asyncio.sleep(paso_poll)
                    estado_orden = await consultar_orden_segura(exchange, orden_id, symbol, precio_orden)
                    status_actual = str(estado_orden.get("status", "")).lower()
                    filled_actual = float(estado_orden.get("filled", 0.0) or 0.0)
                    if status_actual in ("closed", "filled") or filled_actual >= contratos:
                        break
                    fue_cancelada_postonly = status_actual in ("canceled", "cancelled", "rejected", "expired")
                    if fue_cancelada_postonly and (not permitir_repeg or repegs_hechos >= 2 or filled_actual > 0.0):
                        break

                elapsed = time.perf_counter() - ts_inicio
                m_part = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
                if m_part is not None and 0.0 < filled_actual < contratos:
                    _, ttl_efectivo = mrfp.evaluar_extension_fill_parcial_en_cola(
                        dir_norm,
                        contratos,
                        filled_actual,
                        m_part.ofi_profundo,
                        m_part.hurst,
                        elapsed,
                        ttl_max,
                    )
                if permitir_repeg and filled_actual <= 0.0 and elapsed >= 0.25:
                    await self._refrescar_punta_libro_en_cola(exchange, symbol)

                ahora_wall = time.time()
                m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
                if m_live is not None and filled_actual <= 0.0 and permitir_repeg:
                    q_l1_now = m_live.bid_qty if dir_norm == "LONG" else m_live.ask_qty
                    q_opp_now = m_live.ask_qty if dir_norm == "LONG" else m_live.bid_qty
                    q_l1_ratio_last = round(q_l1_now / max(1e-9, q_l1_init), 4) if q_l1_init > 0.0 else 1.0
                    dt_q = max(0.05, float(elapsed))
                    merma_own_q = max(0.0, q_l1_init - q_l1_now) / max(1e-9, q_l1_init)
                    drain_opp_q = max(0.0, q_opp_init - q_opp_now) / max(1e-9, q_opp_init)
                    fpt_race_ratio_last = round(
                        min(10.0, (merma_own_q / dt_q) / max(0.02, drain_opp_q / dt_q)),
                        4,
                    )
                    vacio_live = float(getattr(m_live, "vacio_l2_ratio", 1.0) or 1.0)
                    imb_live = float(getattr(m_live, "imb_l1", 0.0) or 0.0)
                    cancel_live = float(getattr(m_live, "cancel_net_l1", 0.0) or 0.0)
                    veto_btc_activo = (
                        (dir_norm == "LONG" and ahora_wall < ram.ESTADO_GLOBAL.btc_veto_long_hasta)
                        or (dir_norm == "SHORT" and ahora_wall < ram.ESTADO_GLOBAL.btc_veto_short_hasta)
                    )
                    try:
                        cola_toxica, erosion_adversa = mmm.evaluar_aborto_cola_moallemi(
                            dir_norm,
                            q_l1_init,
                            q_l1_now,
                            m_live.ofi_profundo,
                            m_live.hurst,
                            elapsed,
                            veto_btc_activo,
                            q_opp_inicial=q_opp_init,
                            q_opp_actual=q_opp_now,
                            cancel_net_l1=cancel_live,
                            imb_l1=imb_live,
                            vacio_l2_ratio=vacio_live,
                        )
                    except TypeError:
                        cola_toxica, erosion_adversa = mmm.evaluar_aborto_cola_moallemi(
                            dir_norm,
                            q_l1_init,
                            q_l1_now,
                            m_live.ofi_profundo,
                            m_live.hurst,
                            elapsed,
                            veto_btc_activo,
                            q_opp_inicial=q_opp_init,
                            q_opp_actual=q_opp_now,
                        )
                    if cola_toxica and not fue_cancelada_postonly:
                        try:
                            await exchange.cancel_order(orden_id, symbol)
                        except Exception:
                            pass
                        self.disparos_abortados_cola += 1
                        tag_ab = "[MOALLEMI EARLY-ABORT]" if erosion_adversa else "[EARLY QUEUE ABORT]"
                        ram.log_operativo(
                            f"{etiqueta_log} {tag_ab} {symbol} order cancelled at "
                            f"{elapsed:.2f}s due to adverse queue erosion/shift "
                            f"(Q_L1={q_l1_now:.1f}/{q_l1_init:.1f}, H={m_live.hurst:.2f}, OFI={m_live.ofi_profundo:+.2f})."
                        )
                        abortada_en_cola = True
                        break

                    cola_enterrada = (
                        q_l1_init > 0.0
                        and q_l1_now > (q_l1_init * 2.4)
                        and (m_live.ask - m_live.bid) >= (tick_size * 1.95)
                    )
                    try:
                        listo_jump_250ms = mmm.listo_para_repeg_cola(
                            fue_cancelada_postonly, elapsed, ultimo_repeg_elapsed, vacio_l2_ratio=vacio_live
                        )
                    except TypeError:
                        listo_jump_250ms = mmm.listo_para_repeg_cola(
                            fue_cancelada_postonly, elapsed, ultimo_repeg_elapsed
                        )
                    if repegs_hechos < 2 and listo_jump_250ms:
                        try:
                            salto_ok, px_penny = mmm.evaluar_salto_punta_penny(
                                dir_norm, precio_orden, m_live.bid, m_live.ask, tick_size,
                                m_live.ofi_profundo, m_live.hurst, repegs_hechos,
                                edad_en_nivel_seg=elapsed - ultimo_repeg_elapsed,
                                ofi_ticks_racha=m_live.ofi_ticks_consecutivos,
                                vacio_l2_ratio=vacio_live,
                            )
                        except TypeError:
                            salto_ok, px_penny = mmm.evaluar_salto_punta_penny(
                                dir_norm, precio_orden, m_live.bid, m_live.ask, tick_size,
                                m_live.ofi_profundo, m_live.hurst, repegs_hechos,
                                edad_en_nivel_seg=elapsed - ultimo_repeg_elapsed,
                                ofi_ticks_racha=m_live.ofi_ticks_consecutivos,
                            )
                        nuevo_px = px_penny if salto_ok else calcular_precio_penny_jump(
                            m_live.bid, m_live.ask, tick_size, dir_norm, micro_price=m_live.micro_price
                        )
                        if cola_enterrada and nuevo_px == precio_orden:
                            if dir_norm == "LONG" and (m_live.ask - precio_orden) >= (tick_size * 1.95):
                                nuevo_px = cuantizar_tick(precio_orden + tick_size, tick_size, modo="floor")
                            elif dir_norm == "SHORT" and (precio_orden - m_live.bid) >= (tick_size * 1.95):
                                nuevo_px = cuantizar_tick(precio_orden - tick_size, tick_size, modo="ceil")

                        drift_pct = abs(nuevo_px - precio_inicial) / precio_inicial if precio_inicial > 0.0 else 0.0
                        favorable_escape = (
                            (dir_norm == "LONG" and nuevo_px > precio_orden and m_live.ofi_profundo >= (cfg.OFI_MIN_ENTRADA * 0.70))
                            or (dir_norm == "SHORT" and nuevo_px < precio_orden and m_live.ofi_profundo <= (cfg.OFI_MAX_ENTRADA_SHORT * 0.70))
                        )
                        if favorable_escape and 0.0 < drift_pct <= cfg.REPEG_DRIFT_MAX_PCT:
                            try:
                                if not fue_cancelada_postonly:
                                    await exchange.cancel_order(orden_id, symbol)
                                    if not cfg.es_modo_test():
                                        est_pre_repeg = await consultar_orden_segura(exchange, orden_id, symbol, precio_orden)
                                        if float(est_pre_repeg.get("filled", 0.0) or 0.0) > 0.0:
                                            estado_orden = est_pre_repeg
                                            break
                                nueva_orden = await exchange.create_order(
                                    symbol,
                                    "limit",
                                    side_ccxt,
                                    contratos,
                                    nuevo_px,
                                    params_post_only,
                                )
                                orden_id = str(nueva_orden.get("id", orden_id))
                                precio_orden = nuevo_px
                                estado_orden = nueva_orden
                                q_l1_init = max(1.0, q_l1_now)
                                repegs_hechos += 1
                                ultimo_repeg_elapsed = elapsed
                                self.disparos_repeg_ejecutados += 1
                                ram.log_operativo(
                                    f"[MOALLEMI QUEUE-JUMP 250ms] {symbol} {dir_norm} re-pegged step #{repegs_hechos} "
                                    f"to {nuevo_px} at {elapsed:.2f}s (OFI={m_live.ofi_profundo:+.2f} | Order {orden_id})."
                                )
                            except Exception:
                                repegs_hechos = 2
                        elif fue_cancelada_postonly:
                            break

            filled_final = float(estado_orden.get("filled", 0.0) or 0.0)
            status_final = str(estado_orden.get("status", "")).lower()

            if filled_final < contratos and status_final not in ("closed", "filled"):
                try:
                    await exchange.cancel_order(orden_id, symbol)
                except Exception:
                    pass
                try:
                    estado_post = await consultar_orden_segura(exchange, orden_id, symbol, precio_orden)
                    filled_post = float(estado_post.get("filled", 0.0) or 0.0)
                    if filled_post > filled_final:
                        filled_final = filled_post
                        estado_orden = estado_post
                    if filled_final <= 0.0 and hasattr(exchange, "fetch_positions") and not str(orden_id).startswith("oid-"):
                        await asyncio.sleep(0.15)
                        pos_list = await exchange.fetch_positions([symbol])
                        for p_chk in (pos_list or []):
                            if str(p_chk.get("symbol", "")) == symbol:
                                c_chk = abs(float(p_chk.get("contracts") or p_chk.get("info", {}).get("size") or 0.0))
                                if c_chk > 0.0:
                                    filled_final = c_chk
                                    px_chk = float(p_chk.get("entryPrice") or p_chk.get("info", {}).get("avgPrice") or precio_orden)
                                    estado_orden = {"id": orden_id, "status": "closed", "filled": c_chk, "average": px_chk, "price": px_chk}
                                    ram.log_operativo(
                                        f"{etiqueta_log} [ORPHAN-SHIELD] Late fill captured via UTA position sync on {symbol}: "
                                        f"{c_chk} contracts @ {px_chk} adopted into active slot."
                                    )
                                    break
                except Exception:
                    pass

            m_end = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
            vol_bv = float(senal.get("volatilidad_bv", cfg.VOLATILIDAD_BV_PISO_MIN))
            vol_bv_raw = float(senal.get("volatilidad_bv_raw", getattr(m_end, "volatilidad_bv_raw", vol_bv)) or vol_bv)
            pct_24h = float(senal.get("percentil_24h", getattr(m_end, "percentil_24h", 0.50)) or 0.50)
            etiqueta_pct = str(senal.get("etiqueta_percentil") or getattr(m_end, "etiqueta_percentil", "") or pct_24h)
            vacio_l2_in = float(senal.get("vacio_l2_ratio", getattr(m_end, "vacio_l2_ratio", 1.0)) or 1.0)
            imb_l1_in = float(senal.get("imb_l1", getattr(m_end, "imb_l1", 0.0)) or 0.0)
            cancel_l1_in = float(senal.get("cancel_net_l1", getattr(m_end, "cancel_net_l1", 0.0)) or 0.0)
            irrev_in = float(senal.get("irrev_lob", getattr(m_end, "irrev_lob", 0.0)) or 0.0)

            if filled_final <= 0.0:
                esc_opsr = "OPSR_QUEUE_ABORT" if abortada_en_cola else "OPSR_TTL_EXPIRED"
                vec_opsr = {
                    "z_entry": z_val,
                    "dp_pct": round(float(senal.get("dp_pct", 0.0)) * 100.0, 4),
                    "ema900_pct": round(float(senal.get("ema900_pct", 0.0)) * 100.0, 4),
                    "ofi_entry": ofi_val,
                    "hurst_entry": hurst_val,
                    "hawkes_entry": float(senal.get("hawkes", 0.0)),
                    "lyapunov_entry": float(senal.get("lyapunov", 0.0)),
                    "volatilidad_bv": vol_bv,
                    "volatilidad_bv_raw": vol_bv_raw,
                    "percentil_24h": etiqueta_pct,
                    "vacio_l2_ratio": round(vacio_l2_in, 3),
                    "imb_l1": round(imb_l1_in, 4),
                    "cancel_net_l1": round(cancel_l1_in, 4),
                    "irrev_lob": round(irrev_in, 4),
                    "q_l1_ratio": q_l1_ratio_last,
                    "fpt_race_ratio": fpt_race_ratio_last,
                }
                ram.ESTADO_GLOBAL.encolar_auditoria_forense_15s(
                    symbol,
                    dir_norm,
                    esc_opsr,
                    f"repeg={repegs_hechos}",
                    precio_orden,
                    vec_opsr,
                )
                if not abortada_en_cola:
                    ram.log_operativo(
                        f"{etiqueta_log} Order on {symbol} unfilled after {ttl_max:.1f}s "
                        f"(RePegs={repegs_hechos}): margin released."
                    )
                return None

            if not mrfp.validar_lote_ejecutado_suficiente(contratos, filled_final):
                side_dust = "sell" if dir_norm == "LONG" else "buy"
                try:
                    await exchange.create_order(
                        symbol, "market", side_dust, filled_final, None, {"reduceOnly": True}
                    )
                except Exception:
                    pass
                ram.log_operativo(
                    f"{etiqueta_log} [MIN FILL GUARD] Dust fill on {symbol} "
                    f"({filled_final}/{contratos} < {cfg.FRACCION_MINIMA_FILL_LOTE * 100:.0f}%) "
                    f"evacuated immediately to preserve slot."
                )
                return None

            precio_fill = float(estado_orden.get("average") or estado_orden.get("price") or precio_orden)
            sl_int, sl_srv = calcular_niveles_sl_iniciales(precio_fill, dir_norm, tick_size)
            await self._colocar_sl_servidor_bybit(exchange, symbol, sl_srv, side=dir_norm, tick_size=tick_size)

            try:
                tp_din = mcs.calcular_tp_dinamico_volatilidad(
                    vol_bv, percentil_24h=pct_24h, vacio_l2_ratio=vacio_l2_in, symbol=symbol
                )
            except TypeError:
                tp_din = mcs.calcular_tp_dinamico_volatilidad(vol_bv)
            fee_entrada = abs(filled_final * precio_fill) * cfg.COMISION_MAKER_PCT

            kwargs_pos: Dict[str, Any] = {
                "symbol": symbol,
                "side": dir_norm,
                "contratos": filled_final,
                "contratos_iniciales": filled_final,
                "precio_entrada": precio_fill,
                "timestamp_apertura": time.time(),
                "orden_entrada_id": orden_id,
                "sl_interno": sl_int,
                "sl_bybit": sl_srv,
                "tp_dinamico_pct": round(tp_din, 5),
                "fees_acumulados_usdt": round(fee_entrada, 6),
                "es_entrada_maker": True,
                "kelly_usado": kelly_frac,
                "z_entrada": z_val,
                "ofi_entrada": ofi_val,
                "hurst_entrada": hurst_val,
                "hawkes_entrada": float(senal.get("hawkes", 0.0)),
                "lyapunov_entrada": float(senal.get("lyapunov", 0.0)),
                "ema900_entrada_pct": float(senal.get("ema900_pct", 0.0)),
                "dp_entrada_pct": float(senal.get("dp_pct", 0.0)),
                "volatilidad_bv_entrada": vol_bv,
                "percentil_entrada": pct_24h,
                "latencia_rtt_ms": round(rtt_ms, 2),
            }
            try:
                pos = ram.PosicionActiva(
                    **kwargs_pos,
                    volatilidad_bv_raw_entrada=vol_bv_raw,
                    irrev_lob_entrada=irrev_in,
                    imb_l1_entrada=imb_l1_in,
                    cancel_net_l1_entrada=cancel_l1_in,
                    vacio_l2_entrada=vacio_l2_in,
                    q_l1_ratio_entrada=q_l1_ratio_last,
                    fpt_race_ratio=fpt_race_ratio_last,
                )
            except TypeError:
                pos = ram.PosicionActiva(**kwargs_pos)

            ram.ESTADO_GLOBAL.posiciones_activas[symbol] = pos
            self.disparos_llenados += 1

            sub_lbl = "Active position" if dir_norm == "LONG" else "Active SHORT position"
            ram.log_operativo(
                f"{etiqueta_log} [TARGET] {sub_lbl} on {symbol}: {filled_final} @ {precio_fill} "
                f"(age 0s / max {int(cfg.TIEMPO_MAX_HOLD_SEG)}s) | "
                f"Internal SL {sl_int} | Bybit SL {sl_srv}"
            )

            tel.notificar_apertura_confirmada(
                symbol=symbol,
                side=dir_norm,
                contratos=filled_final,
                precio_entrada=precio_fill,
                sl_interno=sl_int,
                kelly_frac=kelly_frac,
                z_score=z_val,
                ofi=ofi_val,
                orden_id=orden_id,
            )
            return pos
        finally:
            if pos is None and orden_id and exchange is not None:
                try:
                    await exchange.cancel_order(orden_id, symbol)
                except Exception:
                    pass
            ram.ESTADO_GLOBAL.liberar_lock_pre_fill(symbol)


EJECUTOR_GLOBAL = EjecutorSniperBybit()
def validar_filtros_elasticos_disparo_y_repeg(
    nocional_usdt: float,
    liquidez_l1_usdt: float,
    ofi_actual: float,
    ofi_inicial: float,
    dt_seg: float,
    q_ratio: float,
    es_long: bool,
) -> Tuple[float, bool]:
    """Conecta la cota de liquidez L1 y la guardia de derivada OFI en ejecutor_sniper.py."""
    from ofensiva import micro_motor_maker as _mmm
    from ofensiva import micro_sizing_kelly as _msk
    noc_acotado = _msk.acotar_nocional_por_liquidez_l1_y_racha(
        nocional_kelly_usdt=float(nocional_usdt),
        liquidez_l1_usdt=float(liquidez_l1_usdt),
    )
    repeg_ok = _mmm.autorizar_repeg_con_derivada_ofi(
        ofi_actual=float(ofi_actual),
        ofi_inicial=float(ofi_inicial),
        dt_seg=float(dt_seg),
        q_ratio=float(q_ratio),
        es_long=bool(es_long),
    )
    return noc_acotado, repeg_ok
