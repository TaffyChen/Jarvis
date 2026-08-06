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
      session_id BIGINT DEFAULT NULL COMMENT '所属会话，可空（历史孤儿轮次）',
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
      KEY idx_conv_ts (ts),
      KEY idx_conv_session (session_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='站内对话流水（按会话挂载，保留最近若干条）'
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
      id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
      title VARCHAR(128) NOT NULL DEFAULT '' COMMENT '会话标题（首问摘要）',
      created_at DATETIME(3) NOT NULL COMMENT '创建时间（UTC）',
      updated_at DATETIME(3) NOT NULL COMMENT '最近活跃（UTC）',
      PRIMARY KEY (id),
      KEY idx_chat_session_updated (updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='站内对话会话（左侧历史列表）'
    """,
    """
    CREATE TABLE IF NOT EXISTS market_briefs (
      id BIGINT NOT NULL AUTO_INCREMENT COMMENT '版本主键',
      brief_date DATE NOT NULL COMMENT '交易日（本地日历日）',
      snapshot_json JSON NOT NULL COMMENT '该版冻结盘面硬数据',
      report_md MEDIUMTEXT NOT NULL COMMENT '五段简报正文 Markdown',
      comments_json JSON NOT NULL COMMENT '挂在本版的批注 [{ts,text}]',
      headline VARCHAR(255) NOT NULL DEFAULT '' COMMENT '一句话定性摘要',
      model VARCHAR(64) NOT NULL DEFAULT '' COMMENT '生成所用模型',
      is_final TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否当日定稿（同日至多一条）',
      created_at DATETIME(3) NOT NULL COMMENT '生成时间（UTC）',
      updated_at DATETIME(3) NOT NULL COMMENT '最近更新时间（UTC）',
      PRIMARY KEY (id),
      KEY idx_brief_date (brief_date),
      KEY idx_brief_created (created_at),
      KEY idx_brief_final (brief_date, is_final)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='盘面简报：同日可多版本追加，定稿仅打标不覆盖'
    """,
)


def ensure_schema() -> None:
    if not storage.mysql_enabled():
        return
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        for sql in _TABLES_SQL:
            cur.execute(sql)
        _ensure_conversation_session_column(cur)
        _migrate_daily_reviews_to_briefs(cur)


def _ensure_conversation_session_column(cur) -> None:
    """旧库 conversations 无 session_id 时补列。"""
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'conversations'
          AND COLUMN_NAME = 'session_id'
        """
    )
    row = cur.fetchone() or {}
    if int(row.get("c") or 0) > 0:
        return
    cur.execute(
        """
        ALTER TABLE conversations
          ADD COLUMN session_id BIGINT DEFAULT NULL COMMENT '所属会话，可空' AFTER id,
          ADD KEY idx_conv_session (session_id)
        """
    )


def _migrate_daily_reviews_to_briefs(cur) -> None:
    """旧表 daily_reviews（一天一条）迁入 market_briefs 首版。"""
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'daily_reviews'
        """
    )
    if int((cur.fetchone() or {}).get("c") or 0) == 0:
        return
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'market_briefs'
        """
    )
    if int((cur.fetchone() or {}).get("c") or 0) == 0:
        return
    cur.execute("SELECT COUNT(*) AS c FROM market_briefs")
    if int((cur.fetchone() or {}).get("c") or 0) > 0:
        return
    cur.execute(
        """
        INSERT INTO market_briefs (
          brief_date, snapshot_json, report_md, comments_json, headline, model,
          is_final, created_at, updated_at
        )
        SELECT review_date, snapshot_json, report_md, comments_json, headline, model,
               1, created_at, updated_at
        FROM daily_reviews
        """
    )
