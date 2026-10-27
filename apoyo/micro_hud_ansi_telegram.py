# -*- coding: utf-8 -*-
"""
Micro-Modulo de Apoyo #3: Motor de Colores ANSI en Vivo para CLI HUD (verbot)
con Cero Contaminacion en Disco.
"""
import time
import config_parametros as cfg
import stats_tracker as st

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
    if (
        "[WIN]" in s
        or "[TARGET] Active" in s
        or "RAM SHIELD O(1): APPROVED" in s
        or "[READY TO FIRE]" in s
        or "[TELEGRAM] Startup notification" in s
    ):
        return f"{_ANSI_BOLD_GREEN}{s}{_ANSI_RESET}"
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
    if (
        "[DIAMOND]" in s
        or "[SHIELD]" in s
        or "[WALD-SPRT CREST]" in s
        or "Break-Even Ratchet" in s
        or "Trailing Stop" in s
        or "Bybit server SL" in s
        or "[MOALLEMI QUEUE-JUMP" in s
        or "[PASSIVE ALIGN" in s
    ):
        return f"{_ANSI_BOLD_CYAN}{s}{_ANSI_RESET}"
    if (
        "[RADAR]" in s
        or "[SNIPER] Order " in s
        or "[SHORT-SNIPER] Order " in s
    ):
        return f"{_ANSI_BOLD_MAGENTA}{s}{_ANSI_RESET}"
    if (
        "[SCRATCH]" in s
        or "[MAKER-SCRATCH" in s
        or "[MOALLEMI EARLY-ABORT]" in s
        or "[EARLY QUEUE ABORT]" in s
        or "[MIN FILL GUARD]" in s
        or "[PHANTOM" in s
        or "unfilled after" in s
        or "[WARN]" in s
        or "quarantine" in s
    ):
        return f"{_ANSI_BOLD_YELLOW}{s}{_ANSI_RESET}"
    if "+===" in s or "|  [BLACK BOX]" in s or "|  MAP:" in s or "|  Balance:" in s:
        return f"{_ANSI_BOLD_CYAN}{s}{_ANSI_RESET}"
    if "|  Total PnL:" in s:
        color_pnl = _ANSI_BOLD_RED if "Total PnL: -" in s else _ANSI_BOLD_GREEN
        return f"{color_pnl}{s}{_ANSI_RESET}"
    if (
        "[TRI-CORTEX" in s
        or "[HOT-RELOAD OOS]" in s
        or "[BLACK BOX 1:1]" in s
        or "[RECONCILER]" in s
        or "[QUANTUM OOS EVALUATOR]" in s
        or "[RADAR LIVE 25Hz]" in s
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
        f"{_ANSI_BOLD_CYAN}[WALD-CREST/BE/JUMP]{_ANSI_RESET} | "
        f"{_ANSI_BOLD_MAGENTA}[RADAR/ORDER]{_ANSI_RESET} | "
        f"{_ANSI_BOLD_YELLOW}[SCRATCH/ABORT]{_ANSI_RESET} | "
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


def seguir_log_en_vivo_cli(lineas_iniciales: int = 16) -> None:
    imprimir_hud_verbot_cli(lineas_log=lineas_iniciales)
    print(
        f"{_ANSI_BOLD_CYAN} [STREAMING COLORIZED TELEMETRY (25Hz) - "
        f"Press Ctrl+C to exit view without stopping bot]{_ANSI_RESET}",
        flush=True,
    )
    ruta_log = cfg.obtener_ruta_archivo("ARCHIVO_LOG")
    try:
        while not ruta_log.exists():
            time.sleep(0.2)
        with open(ruta_log, mode="r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            while True:
                linea = fh.readline()
                if linea:
                    col = colorear_linea_log_mobaxterm(linea)
                    if col:
                        print(col, flush=True)
                else:
                    time.sleep(0.05)
    except KeyboardInterrupt:
        print(
            f"\n{_ANSI_BOLD_GREEN} [OK] Live HUD closed safely "
            f"(Doctor Blythe daemon continues running in background).{_ANSI_RESET}",
            flush=True,
        )
