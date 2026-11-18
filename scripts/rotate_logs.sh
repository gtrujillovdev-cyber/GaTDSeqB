#!/usr/bin/env bash
# scripts/rotate_logs.sh - Rotación preventiva de logs en Edge Node (MicroSD Health)
# Comprime logs cuando superan 25 MB y mantiene un máximo de 3 respaldos históricos.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAX_BYTES=26214400 # 25 MB

for log_name in "bot_unified.log" "server.log"; do
    log_path="$BASE_DIR/$log_name"
    if [ -f "$log_path" ]; then
        # Obtener tamaño de forma compatible entre GNU stat (Linux) y BSD stat (macOS)
        file_size=$(stat -c%s "$log_path" 2>/dev/null || stat -f%z "$log_path" 2>/dev/null || echo 0)
        if [ "$file_size" -ge "$MAX_BYTES" ]; then
            timestamp=$(date +"%Y%m%d_%H%M%S")
            archive_path="$BASE_DIR/${log_name}.${timestamp}.gz"
            gzip -c "$log_path" > "$archive_path"
            : > "$log_path"
            echo "[$(date)] Rotated: $log_name ($file_size bytes) -> $(basename "$archive_path")"

            # Purgar copias antiguas reteniendo solo las 3 más recientes
            ls -t "$BASE_DIR/${log_name}".*.gz 2>/dev/null | tail -n +4 | xargs -r rm -f 2>/dev/null || true
        fi
    fi
done
