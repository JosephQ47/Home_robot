#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rule="$script_dir/99-home-robot-serial.rules"

if [[ ${EUID} -ne 0 ]]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi

install -m 0644 "$rule" /etc/udev/rules.d/99-home-robot-serial.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty
echo "Installed. Replug the controller and CH344, then check /dev/robot_mcu, /dev/hmmd_sensor and /dev/hi3516_debug."
