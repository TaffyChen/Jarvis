# Jarvis 部署

本机日常开发用根目录 `bash start.sh`，**不用打镜像**。

`deploy/` 是以后放到服务器上用的：做成 Docker 镜像，再在服务器上用 Docker 跑起来。

## 先分清三件事

| 动作 | 干什么 | 产物 |
|------|--------|------|
| **构建 build** | 把前后端打进 Docker 镜像 | 存在本机 Docker 里，名字一般是 `jarvis:local`，**不是 zip** |
| **导出 save** | 把镜像存成文件，方便拷贝 | `deploy/dist/jarvis-app-20260805-134752-abc1234.tar` |
| **启动 up** | 在某台已装 Docker 的机器上跑容器 | 网站在 `:1690`，另起 MySQL 容器 |

之前脚本把 build + up 写在一起，所以像「打包还要启动」。现在已经拆开。

```bash
bash scripts/deploy.sh build      # 只打包，不启动
bash scripts/deploy.sh save       # 导出 tar
bash scripts/deploy.sh up         # 启动（本机试跑或服务器上跑）
bash scripts/deploy.sh down       # 停止
```

## 打包后到底是什么？

不是普通业务 zip，而是 **Docker 镜像**：

1. 构建后：在 `docker images` 里看到 `jarvis:local`
2. 导出后：得到带时间戳的 **`.tar`**（如 `jarvis-app-20260805-134752-a1b2c3d.tar`）  
   同时更新软链 `jarvis-app-latest.tar` 指向这一份。离线包带日期是常见做法；正式发版也可以再加版本号。
3. 服务器 `docker load` 之后，又变回镜像，再 `up` 启动

镜像里有：前端页面 + 后端程序 + 构建时的 `knowledge/`。  
镜像里**没有**：`.env` 密码、持仓数据。这些运行时再给。

## 服务器要不要装 Docker？

**要。** 这套发布方式默认服务器安装：

- Docker
- Docker Compose 插件（`docker compose`）

不装 Docker 就得在服务器上另装 Python / Node，那是另一条路，目前没按那个做。

## 怎么发到服务器（简单离线包）

在你电脑上：

```bash
bash scripts/deploy.sh build
bash scripts/deploy.sh save
# 得到 deploy/dist/jarvis-app-年月日-时分秒-git短号.tar
```

拷到服务器（示例，目录用 `/opt/jarvis`，不要放在系统根 `/`）：

```bash
ssh 用户@服务器IP 'sudo mkdir -p /opt/jarvis && sudo chown "$USER" /opt/jarvis'
scp deploy/dist/jarvis-app-*.tar  用户@服务器IP:/opt/jarvis/
# 最省事：整仓 clone 到 /opt/jarvis；或至少拷 deploy/ knowledge/ scripts/ .env.example
scp -r deploy knowledge scripts .env.example 用户@服务器IP:/opt/jarvis/
```

服务器上：

```bash
cd /opt/jarvis
cp .env.example .env          # 再编辑：填 Key / 密码，MYSQL 等
docker load -i jarvis-app-*.tar   # 或具体文件名
bash scripts/deploy.sh up
```

浏览器访问：`http://服务器IP:1690`

## 服务器文件放哪

不要放在系统根目录 `/` 下（乱、也不安全）。常见做法：

| 路径 | 说明 |
|------|------|
| **`/opt/jarvis`** | 最常见，第三方/自建软件 |
| `/srv/jarvis` | 也常见，表示对外服务 |
| `/home/你的用户/jarvis` | 个人 VPS 图省事也可以 |

一个目录里通常有：`.env`、`deploy/`、`knowledge/`、`scripts/`，以及 load 进来的镜像（或 tar）。  
数据在 Docker 卷里，不散落在 `/`。

## 另一种：服务器上直接构建

若服务器能 git clone、也能访问外网拉基础镜像：

```bash
git clone ... && cd Jarvis
cp .env.example .env   # 改密码和 Key
bash scripts/deploy.sh up-build
```

这样不用拷 tar，但服务器要会编译（第一次较慢）。

## 数据怎么过去？

- **表结构**：空库第一次启动会跑 `deploy/mysql/init/*.sql`
- **管理员账号**：看 `.env` 的 `AUTH_ACCOUNT` / `AUTH_PASSWORD`
- **持仓等业务数据**：本机执行 `bash deploy/mysql/export-data.sh`，把 dumps 里的 sql 拿到服务器导入  
  **不要把 dumps 提交到 Git**

## 本机开发 vs 上机

| | 本机 `start.sh` | 服务器 `deploy.sh up` |
|--|-----------------|------------------------|
| 前端 | Vite `:5173` | 打进镜像，只开 `:1690` |
| 后端 | 本机 uvicorn | 容器 `jarvis-app` |
| 数据库 | 本机 Docker MySQL | 一起拉起的 MySQL 容器 |

设计原则：镜像不放密码、不放持仓；SQL 只放建表和角色字典。
