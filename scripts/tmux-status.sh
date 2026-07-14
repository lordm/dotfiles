#!/usr/bin/env bash
# Right-hand tmux status payload: load average + memory use.
#
# Two hard rules, learned from a real incident (see tmux.conf / zshrc):
#
#  1. ONE process. tmux re-runs this on every status-interval tick, so anything
#     it forks is paid forever. Everything below is a bash builtin — no awk, no
#     cut, no free(1). The script itself is the only process.
#
#  2. /proc ONLY. Never read hwmon, SMART, or /sys/class/power_supply here.
#     Those issue real device commands (an NVMe SMART read goes through
#     blk_execute_rq and blocks the block layer). Harmless once; corrosive at
#     5-second intervals forever. Temperatures belong in a desktop applet that
#     polls slowly, not in a terminal status bar.

read -r load1 load5 load15 _ < /proc/loadavg

while read -r key value _; do
  case $key in
    MemTotal:)     total=$value ;;
    MemAvailable:) avail=$value; break ;;
  esac
done < /proc/meminfo

mem=$(( (total - avail) * 100 / total ))

printf '%s %s %s  mem %s%%' "$load1" "$load5" "$load15" "$mem"
