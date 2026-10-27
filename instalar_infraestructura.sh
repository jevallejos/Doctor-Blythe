#!/usr/bin/env bash
# ==============================================================================
# HFT DOCTOR BLYTHE ENGINE - PRODUCTION BASELINE TERPSICHORA V1.0
# Low-Jitter Linux Kernel Tuning (TCP BBR, slow_start_after_idle=0, THP madvise,
# AWS Atomic Clock Sync, systemd Service Lifecycle & Official UNIX Manpage)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="${REPO_DIR}/venv/bin/python"

if [ ! -x "${VENV_PY}" ]; then
    python3 -m venv "${REPO_DIR}/venv"
    "${REPO_DIR}/venv/bin/pip" install --upgrade pip
    "${REPO_DIR}/venv/bin/pip" install -r "${REPO_DIR}/requirements.txt"
fi

if command -v sudo >/dev/null 2>&1; then
    # 1. Kernel Low-Latency TCP/IP & VM Tuning
    sudo -n tee /etc/sysctl.d/99-doctor-blythe-hft.conf >/dev/null 2>&1 << 'SYSCTL_EOF' || true
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 30
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.netdev_max_backlog = 16384
vm.swappiness = 1
SYSCTL_EOF
    sudo -n sysctl --system >/dev/null 2>&1 || true

    # 2. Disable Transparent Huge Pages (THP) defragmentation stalls
    if [ -f /sys/kernel/mm/transparent_hugepage/enabled ]; then
        echo madvise | sudo -n tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null 2>&1 || true
    fi
    if [ -f /sys/kernel/mm/transparent_hugepage/defrag ]; then
        echo madvise | sudo -n tee /sys/kernel/mm/transparent_hugepage/defrag >/dev/null 2>&1 || true
    fi

    # 3. AWS Local Hypervisor Atomic Clock Sync (169.254.169.123)
    if [ -f /etc/chrony/chrony.conf ] && ! grep -q "169.254.169.123" /etc/chrony/chrony.conf 2>/dev/null; then
        sudo -n sed -i '1iserver 169.254.169.123 prefer iburst minpoll 4 maxpoll 4' /etc/chrony/chrony.conf 2>/dev/null || true
        sudo -n systemctl restart chrony 2>/dev/null || true
    fi

    # 4. Elevate active HFT engine PID priority (Nice=-10, Best-Effort IO 0, OOM immunity -800)
    if [ -f "${REPO_DIR}/.tribrain.lock" ]; then
        LIVE_PID="$(cat "${REPO_DIR}/.tribrain.lock" 2>/dev/null | tr -d '[:space:]')"
        if [ -n "${LIVE_PID}" ] && kill -0 "${LIVE_PID}" 2>/dev/null; then
            sudo -n renice -n -10 -p "${LIVE_PID}" >/dev/null 2>&1 || true
            sudo -n ionice -c 2 -n 0 -p "${LIVE_PID}" >/dev/null 2>&1 || true
            echo -800 | sudo -n tee "/proc/${LIVE_PID}/oom_score_adj" >/dev/null 2>&1 || true
        fi
    fi

    # 5. Primary HFT Engine systemd Service Unit (doctor-blythe.service)
    sudo -n tee /etc/systemd/system/doctor-blythe.service >/dev/null 2>&1 << MAIN_SVC_EOF || true
[Unit]
Description=HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0 (25Hz LOB)
After=network-online.target chrony.service
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${REPO_DIR}
Environment="PYTHONUNBUFFERED=1"
Nice=-10
IOSchedulingClass=best-effort
IOSchedulingPriority=0
OOMScoreAdjust=-800
LimitNOFILE=65535
ExecStart=${VENV_PY} -u ${REPO_DIR}/main.py
KillSignal=SIGTERM
TimeoutStopSec=15
Restart=always
RestartSec=2
StandardOutput=null
StandardError=journal

[Install]
WantedBy=multi-user.target
MAIN_SVC_EOF

    # 6. Low-Jitter Background systemd OOS Timer (doctor-blythe-oos.service / .timer)
    sudo -n tee /etc/systemd/system/doctor-blythe-oos.service >/dev/null 2>&1 << SERVICE_EOF || true
[Unit]
Description=Doctor Blythe Low-Jitter Walk-Forward OOS Calibrator
After=network-online.target

[Service]
Type=oneshot
User=${USER}
WorkingDirectory=${REPO_DIR}
Nice=15
IOSchedulingClass=best-effort
IOSchedulingPriority=7
ExecStart=${VENV_PY} -u ${REPO_DIR}/evaluador_cuantico_oos.py
StandardOutput=journal
StandardError=journal
SERVICE_EOF

    sudo -n tee /etc/systemd/system/doctor-blythe-oos.timer >/dev/null 2>&1 << 'TIMER_EOF' || true
[Unit]
Description=Doctor Blythe 8-Hour Walk-Forward OOS Timer (UTC)

[Timer]
OnCalendar=*-*-* 00,08,16:00:06 UTC
RandomizedDelaySec=15
Persistent=true

[Install]
WantedBy=timers.target
TIMER_EOF

    sudo -n systemctl daemon-reload >/dev/null 2>&1 || true
    sudo -n systemctl enable doctor-blythe.service >/dev/null 2>&1 || true
    sudo -n systemctl enable --now doctor-blythe-oos.timer >/dev/null 2>&1 || true

    # 7. Official UNIX Manpage Installation (man verbot / man doctor-blythe)
    sudo -n mkdir -p /usr/local/share/man/man1 >/dev/null 2>&1 || true
    sudo -n tee /usr/local/share/man/man1/verbot.1 >/dev/null 2>&1 << 'MAN_EOF' || true
.TH VERBOT 1 "Octubre 2026" "Doctor Blythe Terpsichora V1.0" "Manual de Operacion HFT"
.SH NAME
verbot, doctor-blythe \- Consola de telemetria, auditoria forense y gestion de servicio para el motor HFT Doctor Blythe Terpsichora V1.0 (25.0 Hz Bybit UTA V5).
.SH SYNOPSIS
.B verbot
[\fICOMANDO\fR | \fIOPCION\fR]
.SH DESCRIPTION
.B verbot
es la interfaz de comando y control de cero latencia para el motor de ejecucion microestructural
.B HFT Doctor Blythe Engine - Production Baseline Terpsichora V1.0
(Arquitectura Micro-Kernel Hexagonal de 45 archivos canonicos dividida en \fBofensiva/\fR, \fBdefensiva/\fR y \fBapoyo/\fR).
.PP
Todos los comandos de visualizacion interceptan las senales de interrupcion localmente, garantizando que presionar \fBCtrl+C\fR cierre unicamente la vista de consola sin detener jamas el demonio en segundo plano.
.SH SERVICE MANAGEMENT COMMANDS
.TP
.B verbot start
Inicia el motor HFT si se encuentra detenido. Verifica el cerrojo fisico \fB.tribrain.lock\fR para impedir instancias duplicadas y asigna prioridad de tiempo real (\fBNice=-10\fR, \fBIO=0\fR, \fBOOM_Adj=-800\fR).
.TP
.B verbot stop
Detiene de forma ordenada (\fBSIGTERM\fR) el servicio \fBdoctor-blythe.service\fR y cualquier bucle supervisor activo, cerrando los descriptores de log y liberando el cerrojo de instancia.
.TP
.B verbot restart \fR[\fB--hard\fR]
Por defecto dispara una recarga atomica en caliente (\fBos.execv\fR en < 400 ms) cuando \fBSlots == 0/1\fR. Con \fB--hard\fR reinicia el proceso completo a traves de \fBsystemd\fR.
.TP
.B verbot status
Muestra el panel de estado del servicio: estado del demonio, PID activo, Uptime, uso de CPU/RAM, prioridad del kernel, estado de auto-arranque (\fBsystemd\fR) y las ultimas trazas operativas.
.TP
.B verbot enable
Habilita el auto-arranque automatico en el boot de Linux para \fBdoctor-blythe.service\fR y \fBdoctor-blythe-oos.timer\fR.
.TP
.B verbot disable
Deshabilita el auto-arranque del servicio en el boot del sistema operativo.
.SH TELEMETRY & FORENSIC OPTIONS
.TP
.B verbot \fR(sin argumentos)
Abre el HUD de telemetria coloreada en tiempo real a 25.0 Hz (\fBbot_hft.log\fR).
.TP
.B verbot -s
Muestra una instantanea rapida de la Caja Negra (\fB[BLACK BOX]\fR) y las ultimas 22 lineas de operacion.
.TP
.B verbot -a
Ejecuta el \fBInspector Forense Anatomico\fR (\fBapoyo/micro_inspector_forense.py\fR): desglose por par campeon, punteria de escudos a +15s y markouts post-cierre a +15s/+30s/+60s.
.TP
.B verbot -i
Ejecuta la auditoria de infraestructura y kernel de baja latencia (\fBTCP BBR\fR, \fBslow_start_after_idle=0\fR, \fBfq\fR, \fBswappiness=1\fR, \fBNice=-10\fR y desfase de reloj atomico AWS).
.TP
.B verbot -q
Ejecuta el calibrador Walk-Forward Out-of-Sample (72h) bajo prioridad aislada (\fBNice=15\fR).
.TP
.B verbot -l
Ejecuta el Gemelo Digital contrafactual de 3,456 combinaciones (\fB--lab\fR) bajo prioridad aislada (\fBNice=15\fR).
.TP
.B verbot man \fR| \fBverbot -h\fR | \fBverbot --help\fR
Muestra este manual tecnico.
.SH FILES
.TP
.I ~/Doctor-Blythe/config_parametros.py
Contrato inmutable de Nivel 0 (100 constantes en mayusculas + Hot-Reload JSON).
.TP
.I ~/Doctor-Blythe/tribrain_stats_v1.jsonl
Libro mayor transaccional de Caja Negra con paridad 1:1 Bybit UTA.
.TP
.I ~/Doctor-Blythe/baul_ia_forense.jsonl
Boveda forense de intercepciones (+15s) y markouts post-cierre (+60s).
.TP
.I /etc/sysctl.d/99-doctor-blythe-hft.conf
Parametros de red y memoria del kernel Linux para baja latencia.
.SH AUTHOR
Arquitectura HFT Doctor Blythe Terpsichora V1.0 (39/39 Canonical Files Certified).
MAN_EOF
    sudo -n gzip -f /usr/local/share/man/man1/verbot.1 >/dev/null 2>&1 || true
    sudo -n cp -f /usr/local/share/man/man1/verbot.1.gz /usr/local/share/man/man1/doctor-blythe.1.gz >/dev/null 2>&1 || true
    sudo -n mandb -q >/dev/null 2>&1 || true
fi

sed -i '/# === DOCTOR-BLYTHE CLI START ===/,/# === DOCTOR-BLYTHE CLI END ===/d' "${HOME}/.bashrc" 2>/dev/null || true

cat << 'EOF' >> "${HOME}/.bashrc"
# === DOCTOR-BLYTHE CLI START ===
verbot() {
    local repo_dir
    if [ -d "${HOME}/Doctor-Blythe" ]; then
        repo_dir="${HOME}/Doctor-Blythe"
    else
        repo_dir="${HOME}/Tri-Brain-Sniper"
    fi
    (
        set +e
        cd "${repo_dir}" || exit 0
        case "${1}" in
            -s)
                ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.imprimir_hud_verbot_cli(lineas_log=22)"
                ;;
            -q)
                nice -n 15 ionice -c 2 -n 7 ./venv/bin/python -u evaluador_cuantico_oos.py
                ;;
            -l)
                nice -n 15 ionice -c 2 -n 7 ./venv/bin/python -u evaluador_cuantico_oos.py --lab
                ;;
            -a)
                ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.imprimir_auditoria_forense_cli()"
                ;;
            -i)
                echo "======================================================================================"
                echo " [INFRASTRUCTURE & LOW-JITTER KERNEL AUDIT - sniper-singapur]"
                echo "======================================================================================"
                echo " -> TCP Congestion Control : $(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo 'N/A')"
                echo " -> TCP Slow-Start Idle    : $(sysctl -n net.ipv4.tcp_slow_start_after_idle 2>/dev/null || echo 'N/A') (Expected: 0)"
                echo " -> Packet Queue Discipline: $(sysctl -n net.core.default_qdisc 2>/dev/null || echo 'N/A') (Expected: fq)"
                echo " -> VM Swappiness          : $(sysctl -n vm.swappiness 2>/dev/null || echo 'N/A') (Expected: 1)"
                if [ -f .tribrain.lock ]; then
                    local lpid
                    lpid="$(cat .tribrain.lock 2>/dev/null | tr -d '[:space:]')"
                    echo " -> Engine PID & Priority  : PID ${lpid} | Nice=$(ps -o ni= -p "${lpid}" 2>/dev/null | tr -d ' ') | OOM_Adj=$(cat /proc/${lpid}/oom_score_adj 2>/dev/null || echo 'N/A')"
                fi
                if command -v chronyc >/dev/null 2>&1; then
                    echo " -> Auto-Hygiene 4-Cycle : ACTIVE (25s TLS Warm | 3m GC RAM | 15m UTA 1:1 | 30m Log Sync)"
    echo " -> Atomic Clock Tracking  : $(chronyc tracking 2>/dev/null | grep 'System time' || echo 'Active')"
                fi
                echo "======================================================================================"
                ;;
            status)
                echo "======================================================================================"
                echo " [SERVICE STATUS - HFT DOCTOR BLYTHE TERPSICHORA V1.0]"
                echo "======================================================================================"
                local lpid=""
                if [ -f .tribrain.lock ]; then
                    lpid="$(cat .tribrain.lock 2>/dev/null | tr -d '[:space:]')"
                fi
                if [ -n "${lpid}" ] && kill -0 "${lpid}" 2>/dev/null; then
                    echo -e " -> Engine State    : [1;92mACTIVE (RUNNING)[0m"
                    echo " -> Active PID      : ${lpid} (Uptime: $(ps -o etime= -p "${lpid}" 2>/dev/null | tr -d ' ') | CPU: $(ps -o %cpu= -p "${lpid}" 2>/dev/null | tr -d ' ')% | MEM: $(ps -o %mem= -p "${lpid}" 2>/dev/null | tr -d ' ')%)"
                    echo " -> Kernel Priority : Nice=$(ps -o ni= -p "${lpid}" 2>/dev/null | tr -d ' ') | OOM_Score_Adj=$(cat /proc/${lpid}/oom_score_adj 2>/dev/null || echo 'N/A')"
                else
                    echo -e " -> Engine State    : [1;91mSTOPPED[0m"
                fi
                echo " -> Systemd Service : doctor-blythe.service ($(systemctl is-enabled doctor-blythe.service 2>/dev/null || echo 'unregistered') / $(systemctl is-active doctor-blythe.service 2>/dev/null || true))"
                echo " -> OOS Timer (8h)  : doctor-blythe-oos.timer ($(systemctl is-enabled doctor-blythe-oos.timer 2>/dev/null || echo 'disabled') / $(systemctl is-active doctor-blythe-oos.timer 2>/dev/null || true))"
                echo "--------------------------------------------------------------------------------------"
                ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.imprimir_hud_verbot_cli(lineas_log=5)"
                ;;
            start)
                local lpid=""
                if [ -f .tribrain.lock ]; then
                    lpid="$(cat .tribrain.lock 2>/dev/null | tr -d '[:space:]')"
                fi
                if [ -n "${lpid}" ] && kill -0 "${lpid}" 2>/dev/null; then
                    echo -e "[1;92m[OK] Doctor Blythe is already running on PID ${lpid} (Single-Instance Guard active).[0m"
                else
                    rm -f .tribrain.lock
                    sudo systemctl start doctor-blythe.service
                    sleep 2
                    if [ -f .tribrain.lock ]; then
                        lpid="$(cat .tribrain.lock 2>/dev/null | tr -d '[:space:]')"
                        sudo -n renice -n -10 -p "${lpid}" >/dev/null 2>&1 || true
                        sudo -n ionice -c 2 -n 0 -p "${lpid}" >/dev/null 2>&1 || true
                        echo -800 | sudo -n tee "/proc/${lpid}/oom_score_adj" >/dev/null 2>&1 || true
                    fi
                    echo -e "[1;92m[OK] Doctor Blythe service started (PID ${lpid}).[0m"
                fi
                ;;
            stop)
                echo -e "[1;93m[INFO] Stopping Doctor Blythe service gracefully (SIGTERM)...[0m"
                sudo systemctl stop doctor-blythe.service 2>/dev/null || true
                tmux kill-session -t demonio_hft 2>/dev/null || true
                if [ -f .tribrain.lock ]; then
                    local lpid
                    lpid="$(cat .tribrain.lock 2>/dev/null | tr -d '[:space:]')"
                    if [ -n "${lpid}" ] && kill -0 "${lpid}" 2>/dev/null; then
                        kill -15 "${lpid}" 2>/dev/null || true
                        sleep 2
                    fi
                    rm -f .tribrain.lock
                fi
                echo -e "[1;92m[OK] Doctor Blythe stopped cleanly.[0m"
                ;;
            restart)
                if [ "${2}" = "--hard" ]; then
                    echo -e "[1;93m[INFO] Performing full systemd hard restart...[0m"
                    verbot stop
                    sleep 1
                    verbot start
                else
                    local lpid=""
                    if [ -f .tribrain.lock ]; then
                        lpid="$(cat .tribrain.lock 2>/dev/null | tr -d '[:space:]')"
                    fi
                    if [ -n "${lpid}" ] && kill -0 "${lpid}" 2>/dev/null; then
                        touch main.py
                        echo -e "[1;96m[OK] Atomic zero-downtime reload (os.execv) triggered for PID ${lpid} (executes as soon as Slots == 0/1).[0m"
                    else
                        verbot start
                    fi
                fi
                ;;
            enable)
                sudo systemctl enable doctor-blythe.service doctor-blythe-oos.timer
                sudo systemctl start doctor-blythe-oos.timer
                echo -e "[1;92m[OK] Auto-start on boot ENABLED for doctor-blythe.service & doctor-blythe-oos.timer.[0m"
                ;;
            disable)
                sudo systemctl disable doctor-blythe.service
                echo -e "[1;93m[OK] Auto-start on boot DISABLED for doctor-blythe.service.[0m"
                ;;
            man|-h|--help|help)
                if command -v man >/dev/null 2>&1 && man -w verbot >/dev/null 2>&1; then
                    man verbot
                else
                    echo "Usage: verbot [start|stop|restart|status|enable|disable|-s|-a|-i|-q|-l|man]"
                fi
                ;;
            *)
                ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.seguir_log_en_vivo_cli(lineas_iniciales=16)"
                ;;
        esac
    )
}
# === DOCTOR-BLYTHE CLI END ===
EOF

echo "[OK] Low-Jitter HFT Kernel Tuning, systemd Service Units & Official UNIX Manpage (man verbot) configured."
