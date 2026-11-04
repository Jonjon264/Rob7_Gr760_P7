#!/usr/bin/env bash
# Start one Docker-managed simulator with the Gazebo window on the Linux host.
set -euo pipefail
sim_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
: "${DISPLAY:?Run this command from your desktop session}"
command -v xauth >/dev/null || { echo 'Install xauth on the host to authorize the Gazebo window.' >&2; exit 1; }

sim_runtime="$sim_dir/.runtime"
mkdir -p "$sim_runtime"
chmod 700 "$sim_runtime"
sim_auth_temp="$(mktemp "$sim_runtime/Xauthority.XXXXXX")"
trap 'rm -f "$sim_auth_temp"' EXIT
# FamilyWild lets the same display cookie work with the container hostname.
# The cookie is kept in a private local file and is never printed.
xauth nlist "$DISPLAY" | sed 's/^..../ffff/' | xauth -f "$sim_auth_temp" nmerge -
if [ ! -s "$sim_auth_temp" ]; then
    echo 'No Xauthority cookie found for this display. Check DISPLAY and XAUTHORITY.' >&2
    exit 1
fi
chmod 600 "$sim_auth_temp"
mv "$sim_auth_temp" "$sim_runtime/Xauthority"
export SIM_XAUTHORITY="$sim_runtime/Xauthority"

if [ "$#" -eq 0 ]; then
    set -- up -d sim
fi
sim_compose=(docker compose -f "$sim_dir/docker-compose.yaml" -f "$sim_dir/docker-compose.gui.yaml")
if [ "${SIM_AUDIO:-false}" = true ]; then
    sim_compose+=(-f "$sim_dir/docker-compose.audio.yaml")
fi
if [ "$1" = up ]; then
    if [ "${SIM_WORLD:-aws_hospital}" = aws_hospital ]; then
        python3 "$sim_dir/prepare_hospital.py" --check
    fi
    # Existing install volumes can hide new packages baked into a rebuilt image.
    # Refresh those volumes before the launch needs the world and joystick.
    "${sim_compose[@]}" run --rm --no-deps -T sim sim-build
fi
"${sim_compose[@]}" "$@"
