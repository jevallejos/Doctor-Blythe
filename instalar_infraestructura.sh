#!/usr/bin/env bash
# ==============================================================================
# HFT DOCTOR BLYTHE ENGINE - PRODUCTION BASELINE TERPSICHORA V1.0
# Low-Jitter Linux Kernel Tuning (TCP BBR, slow_start_after_idle=0, THP madvise,
# AWS Atomic Clock Sync, Process Nice/IO Priority Isolation & Colorized HUD)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="${REPO_DIR}/venv/bin/python"

if [ ! -x "${VENV_PY}" ]; then
    python3 -m venv "${REPO_DIR}/venv"
    "${REPO_DIR}/venv/bin/pip" install --upgrade pip
    "${REPO_DIR}/venv/bin/pip" install -r "${REPO_DIR}/requirements.txt"
fi

# 1. Kernel Low-Latency TCP/IP & VM Tuning (Eliminates 80ms post-idle RTT penalty)
if command -v sudo >/dev/null 2>&1; then
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

    # 5. Low-Jitter Background systemd OOS Timer (Nice=15, IOSchedulingPriority=7)
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
    sudo -n systemctl enable --now doctor-blythe-oos.timer >/dev/null 2>&1 || true
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
        if [ "${1}" = "-s" ]; then
            ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.imprimir_hud_verbot_cli(lineas_log=22)"
        elif [ "${1}" = "-q" ]; then
            nice -n 15 ionice -c 2 -n 7 ./venv/bin/python -u evaluador_cuantico_oos.py
        elif [ "${1}" = "-l" ]; then
            nice -n 15 ionice -c 2 -n 7 ./venv/bin/python -u evaluador_cuantico_oos.py --lab
        elif [ "${1}" = "-a" ]; then
            ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.imprimir_auditoria_forense_cli()"
        elif [ "${1}" = "-i" ]; then
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
                echo " -> Atomic Clock Tracking  : $(chronyc tracking 2>/dev/null | grep 'System time' || echo 'Active')"
            fi
            echo "======================================================================================"
        else
            ./venv/bin/python -u -c "import gestor_posiciones as gp; gp.seguir_log_en_vivo_cli(lineas_iniciales=16)"
        fi
    )
}
# === DOCTOR-BLYTHE CLI END ===
EOF

echo "[OK] Low-Jitter HFT Kernel Tuning (BBR, slow_start=0, Nice=-10) & verbot HUD configured."
