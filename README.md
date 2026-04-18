# vid2cat

`vid2cat` 是一个基于 `Python + FastAPI + Jinja2 + SQLite + Node.js + PicGo-Core` 的抖音视频 AI 猫咪图鉴原型系统。

项目当前已经打通以下主链路：

- 抖音链接解析
- 模型 1 视频摘要与优化建议生成
- 模型 2 猫咪人设生成
- 模型 3 猫咪图片生成
- 图片自动上传到图传
- 图鉴详情页展示
- 管理员后台维护 AI 配置与图床配置

本项目当前是可继续演进的 Web 雏形，重点是先把整体产品链路跑通，而不是一开始就做成完整生产系统。

## 1. 项目定位

`vid2cat` 面向“抖音视频 -> AI 分析 -> 猫咪图鉴 -> 生成图展示”的场景，目标是把短视频内容转化成一个带有 AI 解读、角色设定和生成图片的图鉴页面。

当前版本已经包含：

- 首页搜索与解析入口
- 注册与评论雏形
- 管理员后台
- 三模型配置与调用
- 图床接入
- 图鉴详情页展示

## 2. 架构分析

整体可以分成 5 层：

### 2.1 Web 层

负责页面渲染、表单提交、管理员后台和用户交互。

核心文件：

- [app.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/app.py)
- [index.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/index.html)
- [atlas_detail.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/atlas_detail.html)
- [admin_dashboard.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/admin_dashboard.html)

职责：

- 提供首页、注册页、图鉴页、管理员后台
- 处理 `/parse`、`/register`、`/admin/*`、评论提交等请求
- 把数据库数据整理成前端可展示结构

### 2.2 业务服务层

负责抖音解析、三模型链路编排、图鉴数据组装。

核心文件：

- [services.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/services.py)

职责：

- 解析抖音短链和作品页
- 提取 `window._ROUTER_DATA`
- 生成视频摘要、猫咪人设、绘图提示词
- 调用模型 1 / 2 / 3
- 将模型结果拼装为图鉴对象

### 2.3 集成层

负责对接外部 AI 服务和图床服务。

核心文件：

- [integrations.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/integrations.py)
- [upload.js](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/scripts/upload.js)

职责：

- 以 OpenAI 兼容接口形式调用文本模型与图片模型
- 对接 PicGo-Core
- 把模型 3 返回的远程图片或 base64 图片上传到图传

### 2.4 数据层

负责 SQLite 持久化。

核心文件：

- [db.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/db.py)

职责：

- 初始化数据库和表结构
- 初始化默认管理员
- 保存系统配置
- 保存图鉴、评论、用户
- 为图鉴存储三模型输出和图传 URL

### 2.5 前端资源层

负责模板样式与交互脚本。

核心文件：

- [style.css](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/static/style.css)
- [app.js](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/static/app.js)

职责：

- 页面布局样式
- 搜索框与解析输入的简单联动
- 图鉴页图片展示

## 3. 三模型链路

当前三模型已经串联打通。

### 3.1 模型 1

用途：

- 视频解析成功后生成 `AI 摘要`
- 生成 `优化建议`
- 生成更精炼标签

调用位置：

- `services.py` 中的 `generate_video_analysis_with_model1()`

输入：

- 视频标题
- 视频描述
- 作者
- 标签

输出：

- 摘要
- 建议
- 标签
- 原始模型输出

### 3.2 模型 2

用途：

- 根据模型 1 的视频摘要生成完整猫咪人设

调用位置：

- `services.py` 中的 `generate_cat_profile_with_model2()`

输入：

- 视频标题
- 摘要
- 标签

输出字段：

- `breed`
- `skill`
- `power`
- `personality`
- `story`
- `appearance`
- `rarity`
- `image_prompt`

### 3.3 模型 3

用途：

- 根据模型 2 的人设生成猫咪图

调用位置：

- `services.py` 中的 `generate_cat_image_with_model3()`

处理规则：

- 如果返回 `b64_json`，先上传图传
- 如果返回远程图片 URL，先镜像上传图传
- 数据库只保留最终图传 URL 和简要元信息

输出：

- 最终图传 URL
- 绘图提示词
- 图床状态

## 4. 当前页面与功能

### 4.1 首页

页面文件：

- [index.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/index.html)

功能：

- 搜索关键词
- 粘贴抖音链接直接解析
- 查看最近图鉴
- 查看最近注册用户

说明：

- 页面已添加 `<meta name="referrer" content="no-referrer">`

### 4.2 图鉴详情页

页面文件：

- [atlas_detail.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/atlas_detail.html)

功能：

- 展示视频基础信息
- 展示评分
- 展示模型 1 摘要与建议
- 展示模型 2 猫咪人设
- 展示模型 3 生成图
- 展示模型 1 / 2 / 3 原始输出
- 展示图床状态
- 支持评论

说明：

- 页面已添加 `<meta name="referrer" content="no-referrer">`

### 4.3 管理员后台

页面文件：

- [admin_login.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/admin_login.html)
- [admin_password.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/admin_password.html)
- [admin_dashboard.html](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/templates/admin_dashboard.html)

功能：

- 管理员登录
- 首次登录强制改密
- 配置三套模型参数
- 配置图床参数
- 上传测试图片到图床

## 5. 目录结构

```text
vid2cat/
├─ src/vid2cat/
│  ├─ static/
│  │  ├─ app.js
│  │  └─ style.css
│  ├─ templates/
│  │  ├─ index.html
│  │  ├─ atlas_detail.html
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
├─ .env.example
├─ package.json
├─ picgo.config.json
├─ pyproject.toml
└─ uv.lock
```

## 6. 数据库设计概览

SQLite 数据库在运行时会创建到 `data/vid2cat.db`。

主要表：

- `users`
  - 用户与管理员账号
- `atlases`
  - 图鉴主体
  - 包含视频信息、模型输出、猫咪人设、图传 URL
- `comments`
  - 图鉴评论
- `app_settings`
  - 模型配置与图床配置

`atlases` 当前重点字段包括：

- `ai_summary`
- `optimization_tips`
- `model1_output`
- `model2_output`
- `model3_output`
- `cat_profile_json`
- `prompt_scaffold`
- `cat_image_url`
- `cat_image_prompt`
- `image_host_status`

## 7. 安装与启动

### 7.1 Python 依赖

项目使用 `uv` 管理 Python 依赖。

```bash
uv sync
```

### 7.2 Node.js 依赖

项目使用 Node.js 运行 PicGo 图床上传脚本。

```bash
npm install
```

### 7.3 启动 Web 服务

```bash
uv run uvicorn vid2cat.app:app --host 127.0.0.1 --port 8126
```

也可以使用项目脚本入口：

```bash
uv run vid2cat
```

默认入口定义见 [pyproject.toml](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/pyproject.toml)。

## 8. 默认管理员

如果数据库里没有管理员，首次启动会自动创建默认管理员：

- 用户名：`admin`
- 默认密码：`ChangeMe123!`

首次登录后台后会强制修改密码。

后台入口：

- `/admin/login`

## 9. 配置说明

管理员后台当前可配置：

### 9.1 模型配置

- `ai_model_1_api_url`
- `ai_model_1_api_key`
- `ai_model_1_model`
- `ai_model_2_api_url`
- `ai_model_2_api_key`
- `ai_model_2_model`
- `ai_model_3_api_url`
- `ai_model_3_api_key`
- `ai_model_3_model`

### 9.2 图床配置

- `gitee_repo`
- `gitee_branch`
- `gitee_path`
- `gitee_token`
- `gitee_custom_url`
- `extra_upload_token`

环境变量模板见：

- [.env.example](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/.env.example)

## 10. 图床说明

图床链路基于：

- `PicGo-Core`
- `picgo-plugin-github-plus`
- Gitee 仓库作为图床

Node 侧依赖见：

- [package.json](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/package.json)

上传脚本见：

- [upload.js](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/scripts/upload.js)

手动查看上传帮助：

```bash
npm run upload:help
```

## 11. 主要路由

### 11.1 前台路由

- `GET /`
- `POST /parse`
- `GET /register`
- `POST /register`
- `GET /atlas/{atlas_id}`
- `POST /atlas/{atlas_id}/comment`

### 11.2 后台路由

- `GET /admin/login`
- `POST /admin/login`
- `GET /admin/logout`
- `GET /admin/password`
- `POST /admin/password`
- `GET /admin`
- `POST /admin/settings`
- `POST /admin/upload-test`

## 12. 当前限制

当前版本仍然有一些明显限制：

- 抖音搜索仍是占位式搜索结果，不是真正的平台搜索接口
- 抖音视频直链在浏览器预览环境中可能被跨域或外部策略拦截
- 登录态目前只完整覆盖管理员，不是完整用户系统
- 评论、评分、排行榜、审核仍是后续可扩展能力
- 三模型虽然已经串联，但提示词和错误恢复策略仍可继续优化

## 13. 后续建议

建议下一步继续推进：

- 首页图鉴卡片优先展示生成猫咪图，而不是原视频封面
- 增加单独重跑模型 2 / 模型 3 的后台按钮
- 增加分享卡或海报生成
- 增加图鉴收藏、评分、排行榜
- 增加模型调用日志和失败重试

## 14. 适合接手开发的位置

如果后续要继续开发，优先关注以下文件：

- Web 路由与页面逻辑： [app.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/app.py)
- 抖音解析与三模型编排： [services.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/services.py)
- AI 与图床外部集成： [integrations.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/integrations.py)
- 数据持久化： [db.py](file:///c:/Users/guohuiyuan/code/python/douyinwork/vid2cat/src/vid2cat/db.py)
