#!/usr/bin/env python3
"""
Level 7 DAG: Central 25.0 Hz Asynchronous WebSocket Orchestrator, Single-Instance
Physical PID Lock, Bybit UTA Startup Auditor, Autonomous Hot-Reload Loop, and
Atomic os.execv Auto-Respawn for HFT Doctor Blythe Engine -
Production Baseline Terpsichora V1.0.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import signal
import sys
import time
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

import config_parametros as cfg
import core_estado_ram as ram
import ejecutor_sniper as eje
import escudo_tricortex as tri
import gestor_posiciones as gp
import radar_volatilidad as rad
import stats_tracker as st
import telemetria_telegram as tel

load_dotenv()


class CerrojoInstanciaUnica:
    """
    Physical PID single-instance lock (.tribrain.lock) preventing split-brain
    daemon collisions. Automatically routes to .tribrain_test.lock in test mode.
    """

    def __init__(self, ruta_lock: Optional[pathlib.Path] = None) -> None:
        self.ruta: pathlib.Path = (
            ruta_lock if ruta_lock is not None else cfg.obtener_ruta_archivo("ARCHIVO_LOCK")
        )
        self.adquirido: bool = False

    @staticmethod
    def _pid_activo(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def adquirir(self) -> bool:
        my_pid = os.getpid()
        if self.ruta.exists():
            try:
                contenido = self.ruta.read_text(encoding="utf-8").strip()
                old_pid = int(contenido) if contenido.isdigit() else -1
                if old_pid > 0 and old_pid != my_pid and self._pid_activo(old_pid):
                    return False
            except Exception:
                pass
        try:
            self.ruta.write_text(f"{my_pid}\n", encoding="utf-8")
            self.adquirido = True
            return True
        except Exception:
            return False

    def liberar(self) -> None:
        if self.adquirido and self.ruta.exists():
            try:
                contenido = self.ruta.read_text(encoding="utf-8").strip()
                if contenido == str(os.getpid()):
                    self.ruta.unlink(missing_ok=True)
            except Exception:
                pass
        self.adquirido = False


def _capturar_mtimes_codigo() -> Dict[str, float]:
    mtimes: Dict[str, float] = {}
    base = cfg.obtener_ruta_base()
    for nombre in (
        "config_parametros.py",
        "core_estado_ram.py",
        "telemetria_telegram.py",
        "stats_tracker.py",
        "escudo_tricortex.py",
        "radar_volatilidad.py",
        "ejecutor_sniper.py",
        "gestor_posiciones.py",
        "evaluador_cuantico_oos.py",
        "main.py",
    ):
        p = base / nombre
        if p.exists():
            try:
                mtimes[nombre] = p.stat().st_mtime
            except Exception:
                pass
    return mtimes


async def crear_cliente_bybit_uta() -> Any:
    api_key = os.environ.get("BYBIT_API_KEY", "").strip()
    api_secret = os.environ.get("BYBIT_API_SECRET", "").strip()
    try:
        import ccxt.pro as ccxtpro  # type: ignore
        exchange = ccxtpro.bybit(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )
        return exchange
    except Exception:
        import ccxt.async_support as ccxt_async  # type: ignore
        exchange = ccxt_async.bybit(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )
        return exchange


async def auditar_balance_uta_bybit(exchange: Any, silencioso: bool = False) -> Tuple[float, float, float]:
    try:
        bal = await exchange.fetch_balance({"type": "swap"})
        usdt_info = bal.get("USDT") or {}
        total = float(usdt_info.get("total") or bal.get("total", {}).get("USDT") or cfg.CAPITAL_BASE_HISTORICO_USDT)
        free = float(usdt_info.get("free") or bal.get("free", {}).get("USDT") or total)
        used = float(usdt_info.get("used") or bal.get("used", {}).get("USDT") or max(0.0, total - free))
        ram.ESTADO_GLOBAL.actualizar_auditoria_uta(total=total, free=free, locked=used)
        st.GESTOR_ESTADISTICAS.sincronizar_paridad_uta(total, silencioso=silencioso)
        return total, free, used
    except Exception:
        return (
            ram.ESTADO_GLOBAL.total_usdt,
            ram.ESTADO_GLOBAL.free_usdt,
            ram.ESTADO_GLOBAL.locked_usdt,
        )


async def bucle_stream_par(
    exchange: Any,
    symbol: str,
    evento_apagado: asyncio.Event,
) -> None:
    tick_size = 0.0001
    step_size = 0.1
    try:
        if hasattr(exchange, "markets") and exchange.markets and symbol in exchange.markets:
            mkt = exchange.markets[symbol]
            prec = mkt.get("precision") or {}
            if prec.get("price"):
                tick_size = float(prec["price"])
            if prec.get("amount"):
                step_size = float(prec["amount"])
    except Exception:
        pass

    while not evento_apagado.is_set():
        try:
            if hasattr(exchange, "watch_order_book"):
                ob = await exchange.watch_order_book(symbol, limit=50)
            else:
                ob = await exchange.fetch_order_book(symbol, limit=50)
                await asyncio.sleep(cfg.INTERVALO_RADAR_SEG)

            ahora = time.time()
            disparar, side_sig, senal = rad.RADAR_GLOBAL.procesar_instantanea_libro(symbol, ob, ahora)

            pos_activa = ram.ESTADO_GLOBAL.posiciones_activas.get(symbol)
            if pos_activa is not None and not pos_activa.cerrada:
                m_par = ram.ESTADO_GLOBAL.metricas_ticks.get(symbol)
                if m_par is not None and m_par.mid > 0.0:
                    await gp.GESTOR_POSICIONES.evaluar_posicion_activa(
                        exchange=exchange,
                        pos=pos_activa,
                        precio_actual=m_par.mid,
                        best_bid=m_par.bid,
                        best_ask=m_par.ask,
                        ofi_5s=m_par.ofi_5s,
                        tick_size=tick_size,
                        step_size=step_size,
                        ahora=ahora,
                    )
                continue

            if disparar and senal is not None and symbol != cfg.PAR_LIDER_MACRO:
                pos_nueva = await eje.EJECUTOR_GLOBAL.ejecutar_disparo_maker(
                    exchange=exchange,
                    symbol=symbol,
                    side=side_sig,
                    senal=senal,
                    tick_size=tick_size,
                    step_size=step_size,
                )
                if pos_nueva is not None:
                    await auditar_balance_uta_bybit(exchange, silencioso=True)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            rad.RADAR_GLOBAL.resetear_libro_par(symbol)
            ram.log_operativo(f"[RADAR] Stream error on {symbol}: {type(exc).__name__}: {exc}")
            await asyncio.sleep(1.5)


async def bucle_gobernador_mantenimiento(
    exchange: Any,
    evento_apagado: asyncio.Event,
    mtimes_iniciales: Dict[str, float],
) -> None:
    ts_ultimo_panel = time.time()
    ts_ultimo_lpu = 0.0
    ts_ultimo_oos = 0.0

    while not evento_apagado.is_set():
        await asyncio.sleep(1.0)
        ahora = time.time()

        ram.ESTADO_GLOBAL.procesar_cola_forense_15s(ahora)

        if (ahora - ts_ultimo_lpu) >= 45.0:
            ts_ultimo_lpu = ahora
            await tri.ORQUESTADOR_TRICORTEX.sincronizar_matriz_direccional()
            await tri.ORQUESTADOR_TRICORTEX.sincronizar_multiplicador_kelly()

        if (ahora - ts_ultimo_oos) >= 30.0:
            ts_ultimo_oos = ahora
            recargado, _, aplicados = cfg.recargar_calibracion_oos_si_cambio()
            if recargado:
                ram.log_operativo(
                    f"[HOT-RELOAD OOS] Autonomous parameters synchronized from calibracion_oos.json: "
                    f"{aplicados} | Ctrl={ram.ESTADO_GLOBAL.controlador_autonomo}"
                )

        if (ahora - ts_ultimo_panel) >= 300.0:
            ts_ultimo_panel = ahora
            await auditar_balance_uta_bybit(exchange, silencioso=True)
            st.imprimir_panel_caja_negra()
        tel.notificar_inicio_servicio(total_u, free_u, nocional_k, os.getpid())

        if not ram.ESTADO_GLOBAL.posiciones_activas:
            actuales = _capturar_mtimes_codigo()
            if any(actuales.get(k, 0.0) > (v + 0.5) for k, v in mtimes_iniciales.items()):
                ram.log_operativo(
                    "[AUTO-RESPAWN] Updated Python bytecode detected on disk with 0 open positions: "
                    "executing atomic os.execv reload..."
                )
                try:
                    await exchange.close()
                except Exception:
                    pass
                ram.cerrar_descriptores_log()
                os.execv(sys.executable, [sys.executable] + sys.argv)


async def ejecutar_orquestador_principal() -> int:
    cerrojo = CerrojoInstanciaUnica()
    if not cerrojo.adquirir():
        ram.log_operativo("[MAIN] Another instance holds .tribrain.lock. Aborting startup.")
        return 1

    evento_apagado = asyncio.Event()

    def _solicitar_apagado(*_: Any) -> None:
        evento_apagado.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, _solicitar_apagado)
            except NotImplementedError:
                signal.signal(sig, lambda *_: _solicitar_apagado())

    ram.log_operativo("=" * 66)
    ram.log_operativo(f"STARTING CENTRAL CORE {cfg.NOMBRE_ESTRATEGIA}")
    ram.log_operativo("=" * 66)
    ram.log_operativo(
        f"[MAIN] Physical single-instance lock acquired successfully "
        f"(PID {os.getpid()} | Loop: {type(loop).__name__})."
    )
    ram.log_operativo(f"[MAIN] Local timestamped telemetry active in: {cfg.obtener_aux('ARCHIVO_LOG')}")

    exchange = await crear_cliente_bybit_uta()
    try:
        try:
            await exchange.load_markets()
        except Exception:
            pass

        await gp.reconciliar_posiciones_huerfanas_arranque(exchange)
        total_u, free_u, locked_u = await auditar_balance_uta_bybit(exchange, silencioso=False)
        _, margen_k, nocional_k = tri.calcular_dimension_kelly(
            capital_libre_usdt=free_u,
            z_score=-3.0,
            ofi=0.25,
            hurst=0.40,
            side="LONG",
        )
        ram.log_operativo(
            f"[MAIN] UTA USDT Audit -> Total: {total_u:.4f} | Free RAM: {free_u:.4f} | "
            f"Locked: {locked_u:.4f} | Kelly Margin ({cfg.KELLY_FRACCION_BASE * 100:.0f}%): "
            f"{margen_k:.2f} USDT (Notional {cfg.APALANCAMIENTO_OPERATIVO}x: {nocional_k:.2f} USDT) [READY TO FIRE]"
        )
        ram.log_operativo(
            f"[MAIN] Paper Mode: {cfg.MODO_PAPER_TRADING} | Radar: {cfg.FRECUENCIA_RADAR_HZ:.1f}Hz "
            f"({int(cfg.INTERVALO_RADAR_SEG * 1000)}ms) | Entry TTL: {cfg.TTL_ORDEN_ENTRADA_SEG:.1f}s "
            f"(ReQuote={cfg.PERMITIR_REQUOTE_ENTRADA}) | Harvest: +{cfg.COSECHA_TRIZ_ACTIVACION_PCT * 100:.2f}% | "
            f"Internal SL: -{cfg.SL_INTERNO_PCT * 100:.2f}% | Max Hold: {int(cfg.TIEMPO_MAX_HOLD_SEG)}s"
        )
        ram.log_operativo(
            f"[MAIN] Active targets ({len(cfg.UNIVERSO_PARES_TOTAL)} Champions + Leader): "
            f"{', '.join(cfg.UNIVERSO_PARES_TOTAL)}"
        )
        st.imprimir_panel_caja_negra()
        tel.notificar_inicio_servicio(total_u, free_u, nocional_k, os.getpid())

        mtimes_ini = _capturar_mtimes_codigo()
        tareas = [
            asyncio.create_task(bucle_stream_par(exchange, par, evento_apagado))
            for par in cfg.UNIVERSO_PARES_TOTAL
        ]
        tareas.append(
            asyncio.create_task(bucle_gobernador_mantenimiento(exchange, evento_apagado, mtimes_ini))
        )

        await evento_apagado.wait()
        for t in tareas:
            t.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
    finally:
        try:
            await exchange.close()
        except Exception:
            pass
        cerrojo.liberar()
        ram.cerrar_descriptores_log()
    return 0


def main() -> int:
    if sys.platform != "win32":
        try:
            import uvloop  # type: ignore
            uvloop.install()
        except Exception:
            pass
    return asyncio.run(ejecutar_orquestador_principal())


if __name__ == "__main__":
    sys.exit(main())
