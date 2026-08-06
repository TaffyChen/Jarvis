-- Jarvis MySQL schema（空库首次启动时由 docker-entrypoint 执行）
-- 已有数据卷不会重跑；应用启动时 init_storage / init_identity 仍是幂等补齐。

CREATE TABLE IF NOT EXISTS kv_docs (
  doc_name VARCHAR(128) NOT NULL PRIMARY KEY COMMENT '逻辑文档名（遗留键值，业务已迁出后可空）',
  payload LONGTEXT NOT NULL COMMENT '整份 JSON 文本',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='遗留业务文档键值库，新数据请用专用表';

CREATE TABLE IF NOT EXISTS journal_entries (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id BIGINT DEFAULT NULL COMMENT '用户ID，预留多用户；单机历史可空',
  ts DATETIME(3) NOT NULL COMMENT '日记发生时间（UTC）',
  code VARCHAR(16) NOT NULL DEFAULT '' COMMENT '标的代码，如 sz000636；组合级可用 ALL',
  name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '标的或来源名称',
  level VARCHAR(16) NOT NULL DEFAULT '' COMMENT '级别：danger / warning / info',
  msg VARCHAR(512) NOT NULL DEFAULT '' COMMENT '告警或事件原文',
  action VARCHAR(128) NOT NULL DEFAULT '' COMMENT '建议或已执行动作',
  note TEXT NOT NULL COMMENT '用户备注',
  lamps TINYINT DEFAULT NULL COMMENT '记录时五灯红灯数，可空',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (id),
  KEY idx_journal_ts (ts),
  KEY idx_journal_code (code),
  KEY idx_journal_user_ts (user_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='纪律日记：持仓预警与策略留痕，一行一条';

CREATE TABLE IF NOT EXISTS watch_codes (
  code VARCHAR(16) NOT NULL COMMENT '标的代码，如 sz000636',
  sort_no INT NOT NULL DEFAULT 0 COMMENT '展示/保存顺序',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次入库时间',
  PRIMARY KEY (code),
  KEY idx_watch_sort (sort_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='观察池标的（原 stock_codes.json）';

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
  COMMENT='持仓（原 positions.json，一行一票）';

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
  COMMENT='标的分析底稿（原 analyses.json，一行一票）';

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
  COMMENT='对话沉淀认知卡片（原 memory_notes.json）';

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
  COMMENT='策略/规则提案记录（原 strategy_proposals.json）';

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
  COMMENT='站内对话流水（原 conversations.json，保留最近100条）';

CREATE TABLE IF NOT EXISTS roles (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
  code VARCHAR(64) NOT NULL UNIQUE COMMENT '角色编码，如 admin / member',
  name VARCHAR(64) NOT NULL COMMENT '角色显示名',
  description VARCHAR(255) NOT NULL DEFAULT '' COMMENT '说明',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色';

CREATE TABLE IF NOT EXISTS permissions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
  code VARCHAR(64) NOT NULL UNIQUE COMMENT '权限编码，如 data.read',
  name VARCHAR(64) NOT NULL COMMENT '权限显示名',
  description VARCHAR(255) NOT NULL DEFAULT '' COMMENT '说明'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='权限字典';

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id BIGINT NOT NULL COMMENT '角色ID',
  permission_id BIGINT NOT NULL COMMENT '权限ID',
  PRIMARY KEY (role_id, permission_id),
  CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id),
  CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id) REFERENCES permissions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色-权限关联';

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
  account VARCHAR(64) NOT NULL UNIQUE COMMENT '登录账号',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
  display_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '显示名',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户账号';

CREATE TABLE IF NOT EXISTS user_roles (
  user_id BIGINT NOT NULL COMMENT '用户ID',
  role_id BIGINT NOT NULL COMMENT '角色ID',
  PRIMARY KEY (user_id, role_id),
  CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户-角色关联';

CREATE TABLE IF NOT EXISTS auth_sessions (
  token VARCHAR(128) PRIMARY KEY COMMENT '会话令牌',
  user_id BIGINT NOT NULL COMMENT '用户ID',
  expires_at DATETIME NOT NULL COMMENT '过期时间',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  CONSTRAINT fk_sess_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录会话';
