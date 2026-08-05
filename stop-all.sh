#!/bin/bash
# Jarvis - 一键全关入口（转发到 scripts/stop-all.sh）

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/scripts/stop-all.sh" "$@"
