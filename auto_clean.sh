#!/bin/bash
# GaTDSEQ Auto-Cleaner (Runs Daily)
journalctl --vacuum-time=1d
systemctl restart gatdseq-bot
systemctl restart gatdseq-server
sync; echo 3 > /proc/sys/vm/drop_caches
echo "Cleanup performed successfully at $(date)" >> /home/raspberry/GaTDSEQ/cleanup.log
