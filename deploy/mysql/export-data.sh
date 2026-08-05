#!/bin/bash
# 导出业务数据（kv_docs）到本地 dumps/，默认不进 Git。
# 用法: bash deploy/mysql/export-data.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$ROOT/.env"
OUT_DIR="$ROOT/deploy/mysql/dumps"
mkdir -p "$OUT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "未找到 .env"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$OUT_DIR/kv_docs-$STAMP.sql"
docker exec jarvis-mysql mysqldump \
  -u"${MYSQL_USER:-jarvis}" \
  -p"${MYSQL_PASSWORD}" \
  --no-create-info \
  --skip-extended-insert \
  "${MYSQL_DATABASE:-jarvis}" kv_docs \
  > "$OUT"
echo "已导出: $OUT"
echo "导入示例: docker exec -i jarvis-mysql mysql -u${MYSQL_USER:-jarvis} -p… ${MYSQL_DATABASE:-jarvis} < $OUT"
