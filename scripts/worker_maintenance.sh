#!/bin/bash
# ==============================================================================
# GaTDSEQ Worker Node - Self-Healing, Maintenance & Reboot Protocol
# Target: MacBook Pro (Intel Core i5 Haswell, macOS Big Sur 11.7.11)
# ==============================================================================

WORKER_DIR="/Users/GabrielTrujilloVallejo/GaTDSEQ_Worker"
LOG_DIR="$WORKER_DIR/logs"
LOG_FILE="$LOG_DIR/maintenance.log"
DO_REBOOT=false

if [ "$1" = "--reboot" ]; then
    DO_REBOOT=true
fi

mkdir -p "$LOG_DIR"

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1" | tee -a "$LOG_FILE"
}

log "=========================================================="
log ">>> GaTDSEQ Worker Self-Healing & Maintenance Started <<<"

# 1. Check if any critical quantitative/ML task is currently executing
BUSY_PIDS=$(pgrep -f "optimize_fleet.py|run_backtest.py|xgboost_gate.py" | grep -v "$$" | tr '\n' ' ')
if [ -n "$BUSY_PIDS" ]; then
    log "[WARN] Critical worker job in progress (PIDs: $BUSY_PIDS)."
    if [ "$DO_REBOOT" = true ]; then
        log "[POSTPONE] Reboot postponed to protect ongoing calculation."
        exit 0
    else
        log "[NOTICE] Skipping heavy purge while computation is active."
        exit 0
    fi
fi

# 2. Sweep temporary Python bytecode and cached datasets
log "[CLEAN] Purging Python __pycache__ and transient caches..."
find "$WORKER_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find "$WORKER_DIR" -type f -name "*.pyc" -delete 2>/dev/null
find /tmp -name "*.tmp" -mtime +2 -delete 2>/dev/null

# 3. Log Rotation: Truncate large log files (> 25MB) to protect internal SSD
for f in "$LOG_FILE" "$LOG_DIR/launchd_maintenance.log" /var/log/tailscaled.log /var/log/tailscaled.err.log; do
    if [ -f "$f" ]; then
        SIZE=$(stat -f%z "$f" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 26214400 ]; then
            log "[TRUNCATE] Truncating oversized log $f ($(du -h "$f" 2>/dev/null | cut -f1))"
            tail -n 2500 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
        fi
    fi
done

# 4. Native macOS RAM purge (Flushes disk caches and inactive memory)
log "[MEMORY] Flushing inactive RAM pages with /usr/sbin/purge..."
if [ "$(id -u)" -eq 0 ]; then
    /usr/sbin/purge
else
    /usr/sbin/purge 2>/dev/null || true
fi

# 5. Capture Telemetry & Hardware Health Metrics
UPTIME_STR=$(uptime | sed 's/.*up //' | sed 's/,.*//')
LOAD_STR=$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $2, $3, $4}')
DISK_FREE=$(df -h / | tail -n 1 | awk '{print $4}')
BATT_INFO=$(pmset -g batt 2>/dev/null | grep -o "[0-9]*%.*" || echo "AC Power")

# Memory stats via vm_stat
PAGE_SIZE=$(vm_stat | awk '/page size of/ {print $8}' | tr -d '.')
FREE_PAGES=$(vm_stat | awk '/Pages free/ {print $3}' | tr -d '.')
INACT_PAGES=$(vm_stat | awk '/Pages inactive/ {print $3}' | tr -d '.')

if [ -n "$PAGE_SIZE" ] && [ -n "$FREE_PAGES" ] && [ "$PAGE_SIZE" -gt 0 ] 2>/dev/null; then
    FREE_MB=$(( (FREE_PAGES * PAGE_SIZE) / 1048576 ))
    INACT_MB=$(( (INACT_PAGES * PAGE_SIZE) / 1048576 ))
else
    FREE_MB="N/A"
    INACT_MB="N/A"
fi

log "[METRICS] Uptime: $UPTIME_STR | Load: $LOAD_STR | Free RAM: ~${FREE_MB}MB (Inactive: ~${INACT_MB}MB) | SSD Free: $DISK_FREE | Battery: $BATT_INFO"

# 6. Check Tailscale and SSH Connectivity
if ! /usr/local/bin/tailscale status >/dev/null 2>&1; then
    log "[ALERT] Tailscale daemon unreachable. Attempting service kickstart..."
    launchctl kickstart -k system/com.tailscale.tailscaled 2>/dev/null || true
else
    log "[NETWORK] Tailscale Mesh active and healthy."
fi

# 7. Scheduled Reboot Execution (if requested with --reboot)
if [ "$DO_REBOOT" = true ]; then
    log "[REBOOT] Safe scheduled reboot initiated. Syncing filesystems..."
    /bin/sync
    sleep 2
    if [ "$(id -u)" -eq 0 ]; then
        /sbin/shutdown -r now "Scheduled GaTDSEQ Worker Maintenance Reboot"
    else
        log "[ERROR] Reboot requested but script not running with root privileges (UID: $(id -u))."
        log "[INFO] Ensure com.gatdseq.maintenance is registered as a root LaunchDaemon."
    fi
fi

log ">>> GaTDSEQ Worker Maintenance Routine Completed <<<"
exit 0
