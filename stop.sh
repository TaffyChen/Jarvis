#!/bin/bash
# Jarvis - 稳定入口（转发到 scripts/stop.sh）

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/scripts/stop.sh" "$@"
