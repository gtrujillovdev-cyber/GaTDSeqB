#!/bin/bash
# ==============================================================================
# GaTDSEQ Worker Node - Self-Healing & System Maintenance Installer
# Target: MacBook Pro (Intel Core i5 Haswell, macOS Big Sur 11.7.11)
# ==============================================================================

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] This installer must be run as root."
    echo "Usage: sudo bash install_worker_maintenance.sh"
    exit 1
fi

WORKER_DIR="/Users/GabrielTrujilloVallejo/GaTDSEQ_Worker"
SCRIPTS_SRC="$WORKER_DIR/scripts"

echo "=========================================================="
echo ">>> Installing GaTDSEQ Worker Self-Healing Daemon <<<"

# 1. Ensure permissions on maintenance script
chmod +x "$SCRIPTS_SRC/worker_maintenance.sh"
chown GabrielTrujilloVallejo:staff "$SCRIPTS_SRC/worker_maintenance.sh"
echo "[OK] worker_maintenance.sh permissions set."

# 2. Deploy caffeinate system LaunchDaemon
cp "$SCRIPTS_SRC/com.gatdseq.caffeinate.plist" /Library/LaunchDaemons/com.gatdseq.caffeinate.plist
chown root:wheel /Library/LaunchDaemons/com.gatdseq.caffeinate.plist
chmod 644 /Library/LaunchDaemons/com.gatdseq.caffeinate.plist

# Unload user-level caffeinate LaunchAgent if active
su - GabrielTrujilloVallejo -c "launchctl unload ~/Library/LaunchAgents/com.gatdseq.caffeinate.plist 2>/dev/null" || true
rm -f /Users/GabrielTrujilloVallejo/Library/LaunchAgents/com.gatdseq.caffeinate.plist 2>/dev/null

# Load system-level caffeinate LaunchDaemon
launchctl unload /Library/LaunchDaemons/com.gatdseq.caffeinate.plist 2>/dev/null || true
launchctl load -w /Library/LaunchDaemons/com.gatdseq.caffeinate.plist
echo "[OK] System-level caffeinate daemon active in /Library/LaunchDaemons."

# 3. Deploy maintenance & reboot LaunchDaemon (Daily 04:30 AM)
cp "$SCRIPTS_SRC/com.gatdseq.maintenance.plist" /Library/LaunchDaemons/com.gatdseq.maintenance.plist
chown root:wheel /Library/LaunchDaemons/com.gatdseq.maintenance.plist
chmod 644 /Library/LaunchDaemons/com.gatdseq.maintenance.plist

launchctl unload /Library/LaunchDaemons/com.gatdseq.maintenance.plist 2>/dev/null || true
launchctl load -w /Library/LaunchDaemons/com.gatdseq.maintenance.plist
echo "[OK] Maintenance & Reboot scheduler active (Daily 04:30 AM)."

# 4. Power Configuration Hardening (Auto-Restart after power failure)
pmset -a autorestart 1
echo "[OK] Power management: autorestart on AC failure enabled."

# 5. Run test maintenance cycle (without reboot)
echo "=========================================================="
echo ">>> Executing Test Maintenance Run (RAM Purge & Telemetry) <<<"
su - GabrielTrujilloVallejo -c "$SCRIPTS_SRC/worker_maintenance.sh"

echo "=========================================================="
echo ">>> Installation & Verification Completed Successfully <<<"
exit 0
