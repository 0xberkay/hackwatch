#!/bin/sh
# Keeps the hackwatch lab up: restarts it 2 seconds after it dies.
#
# A nuke kills the server on purpose, so for repeated takes run the lab
# through this loop instead of app.py directly. Each restart reseeds the
# database, so every take starts from the same state.
#
#   ./serve.sh [port]    # default 8000
#   Ctrl-C stops the loop.
set -eu

cd "$(dirname "$0")"
port="${1:-8000}"

while :; do
    python3 app.py "$port" || true
    printf '[serve] lab exited; restarting in 2s (Ctrl-C stops the loop)\n'
    sleep 2
done
