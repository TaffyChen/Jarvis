#!/bin/bash
# Jarvis - 稳定入口（转发到 scripts/start.sh）

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/scripts/start.sh" "$@"
