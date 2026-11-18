# 培训机构管理系统 3.3

React + FastAPI + SQLite 的响应式培训机构管理系统，支持电脑和手机访问。

## 功能

- 管理员：客户、老师、学生、课程、签到和账号管理
- 老师：老师档案中直接开通登录账号、生成初始密码、重置密码；登录后查看个人课表和签到
- 学生：完整档案包含学校年级、监护人、地址、内部备注和在读状态；登录后查看课程并签到
- 客户：搜索、状态筛选、增删改、报名后转正式学生
- 客户跟进：保存沟通记录、跟进结果和下次提醒，首页展示到期及逾期待办
- 排课：按日期和老师筛选、老师时间冲突检测、取消和恢复课程
- 运营报表：近 7/30/90 天课次、课时、签到率、招生转化和老师工作量
- 安全：服务端角色权限、Cookie 会话、CSRF、日志脱敏、安全记住登录 30 天
- 移动端：底部主导航、抽屉菜单、卡片列表、底部弹层和安全区域适配
- 登录体验：支持系统密码管理器和自动填充；应用只保存用户名偏好，不把明文密码写入浏览器存储

## 技术栈

- 前端：React 19 + Vite 8（pnpm）
- 后端：FastAPI + Uvicorn
- 数据库：SQLite（WAL、5 秒写入等待、外键开启）
- 部署：Docker / Render 单实例 + 持久磁盘

前端没有引入 UI 框架、路由库或状态管理库。

## 本地开发

安装后端开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

安装前端依赖：

```powershell
pnpm --dir frontend install
```

终端一，启动 API：

```powershell
python backend/app.py
```

终端二，启动 React 开发服务器：

```powershell
pnpm --dir frontend dev
```

打开 http://127.0.0.1:5173 。Vite 会将 `/api` 转发到 8000 端口。

## 本地生产模式

```powershell
pnpm --dir frontend build
python backend/app.py
```

打开 http://127.0.0.1:8000 。FastAPI 会直接提供构建后的 React 页面。

## 测试

```powershell
python -m pytest -q
pnpm --dir frontend build
```

## 初始账号

仅开发数据库首次创建时生成：

- `admin / admin123`
- `teacher1 / 123456`
- `student1 / 123456`

正式部署后应立即修改管理员密码。公开注册只能创建学生账号；老师和管理员账号由管理员在“账号管理”中创建。

## 环境变量

| 变量 | 说明 |
|---|---|
| `APP_ENV` | 生产环境设为 `production` |
| `SECRET_KEY` | 生产环境必填，至少 32 位 |
| `INITIAL_ADMIN_PASSWORD` | 生产环境必填，首次管理员密码，至少 12 位 |
| `DATA_DIR` | SQLite 数据目录，默认项目下的 `data` |
| `PORT` | API 端口，默认 8000 |
| `ALLOWED_HOSTS` | 允许的主机名，逗号分隔 |
| `ALLOW_DEMO_RESET` | 仅开发环境需要时设为 `true` |

生产环境不会写入演示老师、学生或课程，不会开放演示数据重置，也不会显示 API 文档。

## 云端部署

仓库包含 `Dockerfile` 和 `render.yaml`。Render 部署使用单实例和 1 GB 持久磁盘，SQLite 文件保存在 `/app/data`。

SQLite 适合当前约 300 名活跃学生的小型机构。如果未来需要多实例、多机构或出现大量同时写入，应迁移到 PostgreSQL。

部署后还应配置：

1. 正式域名和 HTTPS。
2. 每日复制 `/app/data/tcms.db` 到独立备份存储。
3. 定期执行一次备份恢复演练。
4. 设置准确的 `ALLOWED_HOSTS`，不要长期保留 `*`。
