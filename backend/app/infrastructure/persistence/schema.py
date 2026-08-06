"""业务表 DDL 与建表。"""
from __future__ import annotations

from app.infrastructure.persistence import storage

_TABLES_SQL = (
    """
    CREATE TABLE IF NOT EXISTS watch_codes (
      code VARCHAR(16) NOT NULL COMMENT '标的代码，如 sz000636',
      sort_no INT NOT NULL DEFAULT 0 COMMENT '展示/保存顺序',
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次入库时间',
      PRIMARY KEY (code),
      KEY idx_watch_sort (sort_no)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='观察池标的（原 stock_codes.json）'
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
      code VARCHAR(16) NOT NULL COMMENT '标的代码',
      name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '标的名称，可空',
      buy_price DECIMAL(18,6) NOT NULL COMMENT '成本价',
      shares DECIMAL(18,4) NOT NULL COMMENT '持股数量',
      buy_date DATE DEFAULT NULL COMMENT '建仓日期',
      extra_json JSON DEFAULT NULL COMMENT '预留扩展字段',
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
      PRIMARY KEY (code),
      KEY idx_pos_date (buy_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='持仓（原 positions.json，一行一票）'
    """,
    """
    CREATE TABLE IF NOT EXISTS analyses (
      code VARCHAR(16) NOT NULL COMMENT '标的代码',
      name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '标的名称',
      type VARCHAR(16) NOT NULL DEFAULT 'stock' COMMENT 'stock / etf',
      rating VARCHAR(32) NOT NULL DEFAULT '' COMMENT '自动/展示分类',
      rating_manual VARCHAR(32) DEFAULT NULL COMMENT '手动分类，如排除',
      reason TEXT COMMENT '一句话理由',
      notes TEXT COMMENT '备注与复核说明',
      analysis_json JSON DEFAULT NULL COMMENT '分析要点数组 [{type,text}]',
      etf_json JSON DEFAULT NULL COMMENT 'ETF 扩展信息',
      reviewed_at DATE DEFAULT NULL COMMENT '利空复核日期',
      risk_ok TINYINT DEFAULT NULL COMMENT '利空是否通过：1是 0否 NULL未复核',
      extra_json JSON DEFAULT NULL COMMENT '预留扩展字段',
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
      PRIMARY KEY (code),
      KEY idx_an_type (type),
      KEY idx_an_reviewed (reviewed_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='标的分析底稿（原 analyses.json，一行一票）'
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_notes (
      id VARCHAR(64) NOT NULL COMMENT '卡片ID，如 mem_xxx',
      ts DATETIME(3) NOT NULL COMMENT '沉淀时间（UTC）',
      kind VARCHAR(32) NOT NULL DEFAULT 'insight' COMMENT 'stock/market/preference/error/insight',
      code VARCHAR(16) NOT NULL DEFAULT '' COMMENT '关联标的，可空',
      title VARCHAR(255) NOT NULL DEFAULT '' COMMENT '短标题',
      content TEXT NOT NULL COMMENT '正文',
      tags_json JSON DEFAULT NULL COMMENT '标签数组',
      expires_at VARCHAR(64) DEFAULT NULL COMMENT '过期时间原文，可空',
      source_question VARCHAR(255) NOT NULL DEFAULT '' COMMENT '来源问题摘要',
      status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active 等',
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
      PRIMARY KEY (id),
      KEY idx_mem_ts (ts),
      KEY idx_mem_code (code),
      KEY idx_mem_kind (kind)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='对话沉淀认知卡片（原 memory_notes.json）'
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_proposals (
      id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
      ts DATETIME(3) NOT NULL COMMENT '提案时间（UTC）',
      summary TEXT COMMENT '提案摘要',
      payload_json JSON DEFAULT NULL COMMENT '提案载荷',
      status VARCHAR(32) NOT NULL DEFAULT 'accepted' COMMENT '状态',
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
      PRIMARY KEY (id),
      KEY idx_prop_ts (ts)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='策略/规则提案记录（原 strategy_proposals.json）'
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
      id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
      ts DATETIME(3) NOT NULL COMMENT '对话时间（UTC）',
      question TEXT NOT NULL COMMENT '用户问题',
      answer MEDIUMTEXT COMMENT '模型回答摘要',
      sources_json JSON DEFAULT NULL COMMENT '引用知识来源',
      patch_json JSON DEFAULT NULL COMMENT 'strategy_patch',
      memory_patch_json JSON DEFAULT NULL COMMENT 'memory_patch',
      memories_used_json JSON DEFAULT NULL COMMENT '本轮用到的沉淀',
      tool_trace_json JSON DEFAULT NULL COMMENT '工具调用轨迹',
      retrieve_queries_json JSON DEFAULT NULL COMMENT '检索改写词',
      orchestrator VARCHAR(32) NOT NULL DEFAULT 'graph' COMMENT '编排器标识',
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
      PRIMARY KEY (id),
      KEY idx_conv_ts (ts)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='站内对话流水（原 conversations.json，保留最近100条）'
    """,
)


def ensure_schema() -> None:
    if not storage.mysql_enabled():
        return
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        for sql in _TABLES_SQL:
            cur.execute(sql)
