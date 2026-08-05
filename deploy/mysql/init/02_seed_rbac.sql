-- RBAC 字典数据（不含管理员密码；账号由应用按 AUTH_ACCOUNT / AUTH_PASSWORD 创建）

INSERT IGNORE INTO roles (code, name, description) VALUES
  ('admin', '管理员', '全部权限'),
  ('member', '成员', '日常看盘与持仓，不含用户管理/知识库维护');

INSERT IGNORE INTO permissions (code, name, description) VALUES
  ('data.read', '读取数据', '行情、持仓、分析只读'),
  ('data.write', '写入数据', '改持仓、标的、日记、分析'),
  ('chat.use', '对话', '使用 Jarvis 对话'),
  ('kb.manage', '维护知识库', '编辑 knowledge/*.md 并预览切块'),
  ('kb.reindex', '重建知识库', '重建向量索引'),
  ('user.manage', '用户管理', '管理账号与角色');

INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p
WHERE (r.code = 'admin' AND p.code IN (
  'data.read', 'data.write', 'chat.use', 'kb.manage', 'kb.reindex', 'user.manage'
))
OR (r.code = 'member' AND p.code IN (
  'data.read', 'data.write', 'chat.use'
));
