# 115 媒体管家

> 三端适配的媒体追更管理平台。结合 TMDB 元数据与 115 网盘文件状态，自动检测剧集更新，支持一键转存与离线下载。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Vue 3](https://img.shields.io/badge/Vue-3-4FC08D?logo=vue.js)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python)
![Flask](https://img.shields.io/badge/Flask-3-000?logo=flask)

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **追剧管理** | 搜索 TMDB 添加动漫/电影/电视剧，自动识别季和集 |
| **115 同步** | 扫描 115 网盘目录，解析文件名匹配集数，缓存到本地 |
| **更新检测** | 对比 TMDB 播出日期与本地缓存，智能识别缺失和待更新 |
| **一键转存** | 粘贴 115 分享链接，自动选中缺失集，一键推送到网盘 |
| **云下载** | 磁力链接离线下载到 115 网盘 |
| **分季展示** | VidHub 风格剧集网格，按季分 Tab，每集显示状态 |
| **多端适配** | PC / Pad / 手机 统一体验 |
| **多用户** | 注册登录系统，每人独立追剧列表与 Cookie |



---

## 技术栈

**前端**
- [Vue 3](https://vuejs.org/) + Composition API + TypeScript
- [Vite](https://vitejs.dev/) 构建工具
- [pnpm](https://pnpm.io/) 包管理
- Infuse/Plex 风格深色主题

**后端**
- [Flask](https://flask.palletsprojects.com/) Web 框架
- [SQLite](https://www.sqlite.org/) 数据库（零配置）
- [TMDB API](https://www.themoviedb.org/documentation/api) 元数据源

---

## 快速开始

### 前置要求

- Python 3.9+
- Node.js 18+
- pnpm（可选，可用 npm 代替）

### 1. 克隆并安装

```bash
git clone https://github.com/rainlotus97/115-media-manager.git
cd 115-media-manager

# 安装 Python 依赖
pip3 install flask requests

# 安装前端依赖
cd frontend && pnpm install
```

### 2. 配置 TMDB API Key（可选）

1. 注册 [TMDB 账号](https://www.themoviedb.org/signup)
2. 在 [API 设置页](https://www.themoviedb.org/settings/api) 申请 API Key (v3 auth)
3. 启动后在 Web 界面的「设置 → TMDB」中填入

### 3. 启动

```bash
# 启动后端（生产模式，同时服务前端构建产物）
python3 115-server.py
# 打开 http://localhost:8767

# 或启动开发模式（前端热更新，API 自动代理）
cd frontend && pnpm dev
# 打开 http://localhost:5173
```

### 4. 初次使用

1. 注册账号 → 登录
2. 设置 → 115 网盘 → 粘贴你的 115 Cookie
3. 设置 → TMDB → 填入 API Key（可选）
4. 进入动漫/电影 → + 添加 → 搜索 TMDB → 填写 115 路径
5. 在详情面板点击 🔄 同步 → 扫描 115 目录文件
6. 去 转存工具 粘贴分享链接 → 选择文件 → 一键转存

---

## 获取 115 Cookie

1. 浏览器打开 [115.com](https://115.com) 并登录
2. F12 打开开发者工具 → Application → Cookies
3. 复制 `115.com` 下的所有 Cookie 值
4. 在项目设置页中粘贴保存

---

## 目录结构

```
115Link/
├── 115-server.py           # Flask 后端主程序（含 Pan115 API 封装）
├── server/
│   ├── auth.py             # 用户认证（注册/登录/session）
│   ├── db.py               # SQLite 数据库初始化与迁移
│   ├── decorators.py       # 登录装饰器
│   ├── media.py            # 追剧列表 CRUD
│   ├── sync.py             # 115 目录扫描 + 文件名解析 + TMDB 比对
│   └── tmdb_api.py         # TMDB API 封装
├── frontend/
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   ├── composables/    # 状态管理
│   │   ├── api.ts          # 类型化 API 客户端
│   │   └── types.ts        # TypeScript 类型定义
│   └── vite.config.ts      # 构建配置 + dev proxy
└── README.md
```

---

## 核心功能使用

### 添加追剧

```
动漫 / 电影 / 电视剧 页面 → + 添加
  → 搜索 TMDB（自动识别动画类目）
  → 选中节目 → 填写 115 网盘存储路径
  → 确认添加
```

### 同步 115 目录

```
详情面板 → [🔄 同步]
  → 后端递归扫描 115 目录（支持多季子目录）
  → 解析文件名中的季号和集号
  → 写入本地缓存，对比 TMDB 播出日期
  → 自动判断：已缓存 N 集 / 已更至 N 集
```

### 文件命名规则

支持自动识别的文件名格式：

| 格式 | 示例 |
|------|------|
| `SxxExx` | `S01E02.mp4`, `三次元女友 - S01E02 - 1080p.mkv` |
| `EPxx` | `EP01.mp4` |
| `[xx]` | `[01].mkv`, `[12.5].mkv` |
| `第xx集/話` | `第01集.mp4` |
| 纯数字 | `01.mp4`, `01 标题.mkv` |

### 子目录命名（分季）

| 格式 | 示例 |
|------|------|
| `Season xx` | `Season 01`, `Season 2` |
| `Sxx` | `S01`, `S1` |
| `第x季` | `第1季`, `第02季` |
| 纯数字 | `01`, `1`（需包含视频文件） |

---

## API 文档

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 `{username, password}` |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/session` | 验证 session |
| POST | `/api/auth/logout` | 登出 |

### 媒体库
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/media/list` | 追剧列表（支持 type/region/status 筛选）|
| POST | `/api/media/add` | 添加追剧 |
| GET/PUT/DELETE | `/api/media/:id` | 详情/更新/删除 |
| POST | `/api/media/:id/sync` | 手动同步 115 目录 |
| POST | `/api/media/sync-all` | 同步所有追更中的剧 |
| GET | `/api/media/:id/episodes` | 获取剧集数据（从缓存，不调 TMDB）|

### TMDB
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/tmdb/config` | 获取/设置 API Key |
| GET | `/api/tmdb/search` | 搜索 `?query=&type=` |
| GET | `/api/tmdb/:id` | 节目详情 |
| GET | `/api/tmdb/:id/season/:n` | 单季剧集列表 |

### 115 网盘
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/check-cookie` | 验证 Cookie |
| GET/POST | `/api/cookie` | 获取/设置 Cookie |
| POST | `/api/info` | 查看分享链接文件列表 |
| POST | `/api/save` | 转存文件到网盘 |

### 下载
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/download/cloud` | 添加离线下载任务 |
| GET | `/api/download/tasks` | 查询下载任务列表 |

---

## 开发

```bash
# 前端开发（热更新 + API 代理到 8767）
cd frontend && pnpm dev

# 构建前端
cd frontend && pnpm build

# 类型检查
cd frontend && pnpm vue-tsc --noEmit
```

---

## 许可

[MIT](LICENSE)

---

> **免责声明**：本项目仅供学习交流使用。使用本项目请遵守 115 网盘服务条款，不得用于商业用途或侵犯他人权益。
