# 分支与协作规则

默认分支是 `main`。目标：**协作者不能直接改 `main`**；维护者 `@TaffyChen` 审 PR。你本人已在 Ruleset 开 **bypass**，热修可直推。

## 协作者怎么做

```bash
git clone https://github.com/TaffyChen/Jarvis.git
git checkout main
git pull
git checkout -b feature/你的主题
# 改代码、本地验证
git push -u origin feature/你的主题
```

在 GitHub 上对 `main` 开 Pull Request，等 **Code Owner（TaffyChen）Approve** 后再合并。

协作者不要：

```bash
git push origin main
```

## 维护者（你）

- Ruleset `protect-main` 已把你加入 **Bypass list**
- 可直接 `git push origin main`（远程会提示 Bypassed rule violations，属正常）
- 大改动仍建议走分支 + PR，方便自己留记录；小改 / 文档 / 热修可直推

推之前确认已与远程对齐，避免 non-fast-forward：

```bash
git pull --ff-only origin main
# 提交后
git push origin main
```

## GitHub 上锁了什么

仓库 Ruleset 名称：`protect-main`，作用在 `main`：

| 规则 | 含义 |
|------|------|
| 必须走 Pull Request | 无 bypass 时不能直接推 `main` |
| 至少 1 个 Approve | 没人点赞不能合 |
| Require review from Code Owners | 必须 `@TaffyChen` 审（见 `.github/CODEOWNERS`） |
| Dismiss stale reviews | 又推了新 commit，旧 Approve 作废 |
| Block force pushes | 禁止强推 `main` |
| Restrict deletions | 禁止删除 `main` |
| Bypass（维护者） | 所有者可绕过上述限制直推；协作者没有 |

协作者权限请只给 **Write**，不要给 Admin。更稳妥的做法是不加人、让对方 **Fork 后提 PR**。

## 公开 / 私密

- 个人免费账号：**公开仓**才能用分支规则；私密仓需要 GitHub Pro。
- 可以随时把仓库改回 Private（Settings → General → Change visibility）。
- **改回私密之后**：免费账号上 Ruleset 可能无法继续强制执行，等于锁分支失效，只剩约定。
- **曾经公开过**：别人已经 clone / fork 的副本收不回来。改回私密只阻止后来者浏览 GitHub 网页。

## 不要提交的内容

| 不要进 Git | 原因 |
|------------|------|
| `.env` | 密钥、密码 |
| 旧 `data/*.json`（若本机还有） | 个人持仓/对话，已迁 MySQL，勿再提交 |
| `frontend/dist/`、`deploy/dist/` | 构建产物 |

历史里的 `data/*.json` 已从 git 中清除。本机若还留着，启动会迁进 MySQL；不必再保留该目录。

## 改 Ruleset

GitHub → 本仓库 → **Settings → Rules → Rulesets → protect-main**（含 Bypass list）。
