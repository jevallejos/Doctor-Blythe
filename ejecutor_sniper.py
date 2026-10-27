"""
Level 6A DAG: Pure Moallemi-Stoikov Passive Maker (Limit PostOnly) Execution
Engine with Zero-RTT Micro-Price Pre-Lead (0ms), 250ms Queue-Jump Re-Peg,
Adverse L1 Queue Depletion Abort (<15% Q_L1), Minimum Fill Guard (<15%), and
Pre-Validated Bybit V5 MarkPrice Stop-Loss Geometry (SEI-02) for
HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Dict, Optional, Tuple

import config_parametros as cfg
import micro_motor_maker as mmm
import micro_sizing_kelly as msk
import core_estado_ram as ram
import escudo_tricortex as tri
import radar_volatilidad as rad
import telemetria_telegram as tel


def cuantizar_tick(precio: float, tick_size: float, modo: str = "nearest") -> float:
    if tick_size <= 0.0:
        return round(precio, 6)
    decimales = max(0, int(round(-math.log10(tick_size)))) if tick_size < 1.0 else 2
    unidades = precio / tick_size
    if modo == "floor":
        val = math.floor(unidades + 1e-9) * tick_size
    elif modo == "ceil":
        val = math.ceil(unidades - 1e-9) * tick_size
    else:
        val = round(unidades) * tick_size
    return round(val, decimales)


def cuantizar_lote(cantidad: float, step_size: float) -> float:
    if step_size <= 0.0:
        return round(cantidad, 4)
    decimales = max(0, int(round(-math.log10(step_size)))) if step_size < 1.0 else 0
    val = math.floor((cantidad / step_size) + 1e-9) * step_size
    return round(val, decimales)


def calcular_precio_penny_jump(
    best_bid: float,
    best_ask: float,
    tick_size: float,
    side: str,
    micro_price: float = 0.0,
) -> float:
    """
    Moallemi-Stoikov Zero-RTT Pre-Lead Quoting (t = 0ms):
    Steps 1 tick inside the spread when spread >= 2 ticks (or when Stoikov
    micro-price leads the mid-price), strictly bounded by best_ask - tick_size
    (LONG) or best_bid + tick_size (SHORT) to guarantee 100% PostOnly safety.
    """
    t_size = max(1e-8, float(tick_size))
    spread = best_ask - best_bid
    mid = 0.5 * (best_bid + best_ask)
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"

    if dir_norm == "LONG":
        pre_lead = (micro_price > (mid + 0.15 * spread)) if micro_price > 0.0 else False
        if spread >= (t_size * 1.95) or ( pre_lead and spread >= (t_size * 1.50) ):
            candidato = min(best_ask - t_size, best_bid + (cfg.OFFSET_PENNY_JUMP_TICKS * t_size))
        else:
            candidato = best_bid
        return cuantizar_tick(candidato, t_size, modo="floor")

    pre_lead_s = (micro_price < (mid - 0.15 * spread)) if micro_price > 0.0 else False
    if spread >= (t_size * 1.95) or ( pre_lead_s and spread >= (t_size * 1.50) ):
        candidato = max(best_bid + t_size, best_ask - (cfg.OFFSET_PENNY_JUMP_TICKS * t_size))
    else:
        candidato = best_ask
    return cuantizar_tick(candidato, t_size, modo="ceil")


def calcular_niveles_sl_iniciales(
    precio_entrada: float,
    side: str,
    tick_size: float = 0.0001,
) -> Tuple[float, float]:
    sl_int_pct = float(cfg.SL_INTERNO_PCT)
    sl_bybit_pct = float(cfg.obtener_aux("SL_EMERGENCIA_BYBIT_PCT", 0.0068))
    dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"

    if dir_norm == "LONG":
        sl_int = cuantizar_tick(precio_entrada * (1.0 - sl_int_pct), tick_size, modo="floor")
        sl_srv = cuantizar_tick(precio_entrada * (1.0 - sl_bybit_pct), tick_size, modo="floor")
    else:
        sl_int = cuantizar_tick(precio_entrada * (1.0 + sl_int_pct), tick_size, modo="ceil")
        sl_srv = cuantizar_tick(precio_entrada * (1.0 + sl_bybit_pct), tick_size, modo="ceil")
    return sl_int, sl_srv


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


class EjecutorSniperBybit:
    """
    Moallemi-Stoikov Zero-Adverse-Selection PostOnly Execution Engine.
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
            t_size = max(1e-8, float(tick_size))
            dir_norm = "LONG" if str(side).upper() in ("BUY", "LONG") else "SHORT"
            sl_seguro = float(sl_precio)
            m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
            if m_live is not None and m_live.bid > 0.0 and m_live.ask > 0.0:
                if dir_norm == "LONG" and sl_seguro >= m_live.bid:
                    sl_seguro = cuantizar_tick(m_live.bid - (2.0 * t_size), t_size, modo="floor")
                elif dir_norm == "SHORT" and sl_seguro <= m_live.ask:
                    sl_seguro = cuantizar_tick(m_live.ask + (2.0 * t_size), t_size, modo="ceil")

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
            ob = await exchange.fetch_order_book(symbol, limit=50)
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

            precio_inicial = calcular_precio_penny_jump(
                best_bid, best_ask, tick_size, dir_norm, micro_price=micro_px
            )
            precio_orden = precio_inicial
            z_val = float(senal.get("z_score", 0.0))
            ofi_val = float(senal.get("ofi", 0.0))
            hurst_val = float(senal.get("hurst", 0.42))

            kelly_frac, _, nocional_usdt = msk.calcular_dimension_kelly_uta(
                tri,
                capital_libre_usdt=ram.ESTADO_GLOBAL.free_usdt,
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
            ts_inicio = time.perf_counter()
            paso_poll = min(0.08, max(0.02, ttl_max / 10.0))

            estado_orden = orden
            while (time.perf_counter() - ts_inicio) < ttl_max:
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
                if permitir_repeg and filled_actual <= 0.0 and elapsed >= 0.25:
                    await self._refrescar_punta_libro_en_cola(exchange, symbol)

                ahora_wall = time.time()
                m_live = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
                if m_live is not None and filled_actual <= 0.0 and permitir_repeg:
                    q_l1_now = m_live.bid_qty if dir_norm == "LONG" else m_live.ask_qty
                    erosion_adversa = (
                        q_l1_init > 0.0
                        and q_l1_now > 0.0
                        and (q_l1_now / q_l1_init) < 0.15
                        and (
                            (dir_norm == "LONG" and m_live.ofi_profundo <= -0.10)
                            or (dir_norm == "SHORT" and m_live.ofi_profundo >= 0.10)
                        )
                    )
                    veto_btc_activo = (
                        (dir_norm == "LONG" and ahora_wall < ram.ESTADO_GLOBAL.btc_veto_long_hasta)
                        or (dir_norm == "SHORT" and ahora_wall < ram.ESTADO_GLOBAL.btc_veto_short_hasta)
                    )
                    cola_toxica = (
                        erosion_adversa
                        or (
                            elapsed >= cfg.EARLY_QUEUE_ABORT_SEG
                            and (
                                m_live.hurst > cfg.HURST_TECHO_DURO_ABSOLUTO
                                or veto_btc_activo
                                or (dir_norm == "LONG" and m_live.ofi_profundo <= -0.25)
                                or (dir_norm == "SHORT" and m_live.ofi_profundo >= 0.25)
                            )
                        )
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
                        return None

                    cola_enterrada = (
                        q_l1_init > 0.0
                        and q_l1_now > (q_l1_init * 2.4)
                        and (m_live.ask - m_live.bid) >= (tick_size * 1.95)
                    )
                    listo_jump_250ms = fue_cancelada_postonly or (
                        elapsed >= 0.25
                        and (elapsed - ultimo_repeg_elapsed) >= 0.25
                    )
                    if repegs_hechos < 2 and listo_jump_250ms:
                        nuevo_px = calcular_precio_penny_jump(
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
                    filled_final = max(filled_final, float(estado_post.get("filled", 0.0) or 0.0))
                except Exception:
                    pass

            if filled_final <= 0.0:
                ram.log_operativo(
                    f"{etiqueta_log} Order on {symbol} unfilled after {ttl_max:.1f}s "
                    f"(RePegs={repegs_hechos}): margin released."
                )
                return None

            if (filled_final / contratos) < cfg.FRACCION_MINIMA_FILL_LOTE:
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

            vol_bv = float(senal.get("volatilidad_bv", cfg.VOLATILIDAD_BV_PISO_MIN))
            tp_din = max(
                cfg.COSECHA_ESTANCAMIENTO_MFE_PCT,
                min(0.0032, max(cfg.COSECHA_TRIZ_ACTIVACION_PCT, vol_bv * 3.2)),
            )
            fee_entrada = abs(filled_final * precio_fill) * cfg.COMISION_MAKER_PCT

            pos = ram.PosicionActiva(
                symbol=symbol,
                side=dir_norm,
                contratos=filled_final,
                contratos_iniciales=filled_final,
                precio_entrada=precio_fill,
                timestamp_apertura=time.time(),
                orden_entrada_id=orden_id,
                sl_interno=sl_int,
                sl_bybit=sl_srv,
                tp_dinamico_pct=round(tp_din, 5),
                fees_acumulados_usdt=round(fee_entrada, 6),
                es_entrada_maker=True,
                kelly_usado=kelly_frac,
                z_entrada=z_val,
                ofi_entrada=ofi_val,
                hurst_entrada=hurst_val,
                hawkes_entrada=float(senal.get("hawkes", 0.0)),
                lyapunov_entrada=float(senal.get("lyapunov", 0.0)),
                ema900_entrada_pct=float(senal.get("ema900_pct", 0.0)),
                dp_entrada_pct=float(senal.get("dp_pct", 0.0)),
                volatilidad_bv_entrada=vol_bv,
                percentil_entrada=float(senal.get("percentil_24h", 0.50)),
                latencia_rtt_ms=round(rtt_ms, 2),
            )
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
            ram.ESTADO_GLOBAL.liberar_lock_pre_fill(symbol)


EJECUTOR_GLOBAL = EjecutorSniperBybit()
