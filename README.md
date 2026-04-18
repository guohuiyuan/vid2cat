# vid2cat

`vid2cat` 是一个基于 `Python + FastAPI + Jinja2 + SQLite + Node.js + PicGo-Core` 的抖音驱动猫咪养成 Web 原型。

当前代码的主流程已经从“抖音视频 -> 图鉴展示”转成“注册登录 -> 首次领养 -> 喂养成长 -> 对话陪伴 -> 放入市场 / 重新领养”的养成玩法。

## 当前状态

已经跑通的核心链路：

- 用户注册、登录、退出
- 首次领养显式选择猫咪品种和颜色
- 首次领养支持可选图片链接；如果没有图片，会使用预设提示词自动生成初始形象
- 每个用户最多持有 3 只猫，并支持当前陪伴猫切换
- 对话与喂养共用一个输入框
- 抖音链接喂养走异步任务，完成后刷新猫咪形象与属性
- 猫咪可放入市场，其他用户可重新领养
- 图鉴体系仍保留，可继续解析抖音内容并展示图鉴详情
- 管理员后台可维护三模型与图床配置

## 产品主循环

当前版本的推荐体验路径：

1. 用户注册或登录后进入 `/my-cat`
2. 第一次领养时先选品种和颜色，再决定是否提供图片链接
3. 如果没有图片，系统会基于“喵喵系”预设人设自动生成初始猫图
4. 在统一输入框中输入内容：
   - 普通文本：进入流式聊天
   - 包含抖音链接：进入喂养任务
5. 喂养完成后，猫咪的属性、故事摘要和形象会同步更新
6. 用户可在“我的三只猫”区域切换当前陪伴中的猫
7. 用户可把猫放入市场，其他用户可重新领养

## 喵喵设定

当前代码里，猫咪的人设不再是随机散点，而是统一围绕“喵喵系角色”约束生成：

- 亲人、敏感、聪明，会观察主人的情绪
- 有陪伴欲，也带一点嘴硬心软和小傲娇
- 会把抖音内容理解成自己的成长能量
- 说话自然，不会每句都机械重复“喵”
- 不写成客服或 AI 助手，而是“被主人养熟的小猫”

这套基础设定已经统一接入：

- 初始领养提示词
- 图鉴态猫设生成
- 成长终局猫设生成
- 日常聊天系统提示词

相关实现主要在：

- `src/vid2cat/services.py`
- `src/vid2cat/db.py`

## 技术栈

- Python 3.12+
- FastAPI
- Jinja2
- SQLite
- httpx
- json-repair
- Node.js
- PicGo-Core

## 目录结构

```text
vid2cat/
├─ src/vid2cat/
│  ├─ static/
│  │  ├─ app.js
│  │  └─ style.css
│  ├─ templates/
│  │  ├─ index.html
│  │  ├─ my_cat.html
│  │  ├─ plaza.html
│  │  ├─ atlas_list.html
│  │  ├─ atlas_detail.html
│  │  ├─ login.html
│  │  ├─ register.html
│  │  ├─ admin_login.html
│  │  ├─ admin_password.html
│  │  └─ admin_dashboard.html
│  ├─ app.py
│  ├─ db.py
│  ├─ integrations.py
│  ├─ services.py
│  └─ __init__.py
├─ scripts/
│  └─ upload.js
├─ data/
├─ package.json
├─ pyproject.toml
└─ README.md
```

## 代码分层

### 1. Web 层

负责路由、模板渲染、表单提交、异步接口输出。

核心文件：

- `src/vid2cat/app.py`

主要职责：

- 用户注册登录
- 我的猫页面与市场页面
- 图鉴相关页面
- 喂养异步任务与聊天流式接口
- 管理员后台

### 2. 业务服务层

负责抖音解析、AI 设定生成、图片生成与聊天人设。

核心文件：

- `src/vid2cat/services.py`

主要职责：

- 解析抖音链接与页面数据
- 模型 1 生成视频分析
- 模型 2 生成人设与对话人格
- 模型 3 生成猫咪图像
- 维护统一的“喵喵系角色”设定

### 3. 数据层

负责 SQLite 表结构初始化和增删改查。

核心文件：

- `src/vid2cat/db.py`

主要职责：

- 用户、猫咪、喂养记录、消息、图鉴、评论、评分、系统配置的持久化
- 默认管理员初始化
- 历史数据库迁移

### 4. 集成层

负责 AI 模型调用和图床上传。

核心文件：

- `src/vid2cat/integrations.py`
- `scripts/upload.js`

## 三模型链路

### 模型 1：视频分析

用途：

- 根据抖音作品生成结构化摘要
- 输出标签、建议和分数
- 为喂养事件提供属性变化依据

### 模型 2：猫设生成

用途：

- 生成图鉴态猫设
- 生成首次领养的人设
- 生成成长终局的人设
- 为聊天提供稳定人格

输出字段：

- `name`
- `breed`
- `skill`
- `power`
- `personality`
- `story`
- `appearance`
- `rarity`
- `image_prompt`

### 模型 3：图像生成

用途：

- 根据模型 2 的设定和绘图提示词生成猫图

处理规则：

- 若返回 `b64_json`，则先上传图床
- 若返回远程图片 URL，则镜像上传图床
- 数据库只保留最终可访问 URL

## 当前页面

### 我的猫 `/my-cat`

当前是主页面，包含：

- “我的三只猫”卡片切换区
- 首次领养 / 再领养入口
- 当前猫咪形象与属性
- 统一对话/喂养输入框
- 成长记录
- 新用户专属成长说明

### 猫咪市场 `/plaza`

包含：

- 已公开展示的猫咪
- 已被放入市场等待重新领养的猫咪
- 登录后重新领养操作

### 图鉴相关

仍保留原图鉴能力：

- `/atlases`
- `/atlas/{atlas_id}`

用于兼容原“抖音视频 -> 图鉴”链路，以及管理员提示词参考。

### 管理员后台

包括：

- `/admin/login`
- `/admin/password`
- `/admin`

支持：

- 模型 1 / 2 / 3 配置
- 图床配置
- 图床上传测试

## 数据模型

SQLite 数据库默认位于：

- `data/vid2cat.db`

当前主要表：

- `users`
- `cats`
- `cat_feed_records`
- `cat_messages`
- `atlases`
- `comments`
- `ratings`
- `app_settings`

### `cats`

当前承载：

- 当前用户拥有的猫
- 当前陪伴状态 `is_active`
- 市场状态 `is_public` / `available_for_adoption`
- 当前形象 `image_url`
- 当前人格 `personality`
- 当前故事 `story_summary`

### `cat_feed_records`

记录每次喂养：

- 来源链接
- 视频标题 / 作者 / 摘要
- 标签摘要
- 五维属性变化
- 模型 1 原始输出

### `cat_messages`

记录与当前猫的聊天消息，用于持续塑造陪伴感与上下文。

## 主要路由

### 用户主流程

- `GET /`：重定向到 `/my-cat`
- `GET /register`
- `POST /register`
- `GET /login`
- `POST /login`
- `GET /logout`
- `GET /my-cat`
- `POST /my-cat/adopt`
- `POST /my-cat/adopt-new`
- `POST /my-cat/switch`
- `POST /my-cat/release`
- `POST /my-cat/publish`

### 异步与交互接口

- `POST /api/my-cat/chat/stream`
- `POST /api/my-cat/feed`
- `GET /api/tasks/{task_id}`

### 图鉴与社区相关

- `GET /atlases`
- `GET /atlas/{atlas_id}`
- `POST /atlas/{atlas_id}/comment`
- `POST /atlas/{atlas_id}/rating`
- `GET /plaza`
- `POST /plaza/adopt`

## 安装与启动

### 1. 安装 Python 依赖

```bash
uv sync
```

### 2. 安装 Node.js 依赖

```bash
npm install
```

### 3. 启动服务

```bash
uv run uvicorn vid2cat.app:app --host 127.0.0.1 --port 8126
```

或使用项目入口：

```bash
uv run vid2cat
```

`pyproject.toml` 中的入口为：

```toml
[project.scripts]
vid2cat = "vid2cat:main"
```

## 管理员账号

首次启动若数据库内没有管理员，会自动创建：

- 用户名：`admin`
- 密码：`ChangeMe123!`

首次登录后台后会强制修改密码。

## 配置项

当前后台可配置：

### 模型配置

- `ai_model_1_api_url`
- `ai_model_1_api_key`
- `ai_model_1_model`
- `ai_model_2_api_url`
- `ai_model_2_api_key`
- `ai_model_2_model`
- `ai_model_3_api_url`
- `ai_model_3_api_key`
- `ai_model_3_model`

### 图床配置

- `gitee_repo`
- `gitee_branch`
- `gitee_path`
- `gitee_token`
- `gitee_custom_url`
- `extra_upload_token`

## 前端交互说明

### 统一输入框

`src/vid2cat/static/app.js` 当前会自动识别输入内容：

- 命中抖音链接域名：提交喂养任务
- 普通文本：走流式聊天

### 异步喂养

喂养过程不是同步阻塞，而是：

1. 提交任务
2. 轮询任务状态
3. 展示“分析中 / 生图中 / 已完成”
4. 完成后回到 `/my-cat`

## 已知限制

- 抖音搜索结果仍以占位候选为主，不是真正的平台搜索
- 市场目前是“公开展示 + 重新领养”模式，还不是完整社区
- 聊天与人设质量高度依赖模型 2 的稳定性
- 模型 3 和图床链路失败时，仍需要更多重试与回退策略
- “图鉴体系”和“猫咪养成体系”目前并存，后续还可以继续梳理

## 下一步建议

- 为首次领养补“本地图片上传”而不只是图片链接
- 为喂养任务增加失败重试和超时提示
- 在市场里补更多状态标签与排序
- 把“喵喵设定”进一步拆成后台可配置模板
- 增加猫咪详情页或市场详情页，展示完整成长轨迹
