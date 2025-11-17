# 开发指南

本文档说明如何编译前端、后端并重启服务器。

## 前端编译

### 开发模式（不嵌入到后端）

```bash
cd web
pnpm dev
```

前端会运行在 http://localhost:5173，支持热重载。

### 生产模式（嵌入到后端）

```bash
cd web
pnpm release
```

这个命令会：
1. 构建前端生产版本
2. 自动将构建结果复制到 `server/router/frontend/dist/`
3. 后端使用 `//go:embed` 在编译时将这些文件嵌入到可执行文件中

**重要**：修改前端代码后，必须同时重新编译后端才能看到效果。

## 后端编译

### 编译

```bash
go build -o memos.exe ./cmd/memos
```

在 Linux/Mac 上：
```bash
go build -o memos ./cmd/memos
```

### 运行测试

```bash
go test ./...
```

## 重启服务器

### 1. 停止当前服务器

**Windows:**
```bash
# 查找占用端口的进程
netstat -ano | findstr :8081

# 杀死进程（替换 PID）
taskkill //F //PID <PID>
```

**Linux/Mac:**
```bash
# 查找占用端口的进程
lsof -i :8081

# 杀死进程（替换 PID）
kill -9 <PID>
```

### 2. 启动服务器

**开发模式:**
```bash
./memos.exe --mode dev --port 8081
```

**生产模式:**
```bash
./memos.exe --mode prod --port 8081
```

### 后台运行（Linux/Mac）

```bash
nohup ./memos --mode dev --port 8081 > memos.log 2>&1 &
```

### 后台运行（Windows）

```bash
start /B memos.exe --mode dev --port 8081
```

## 完整的修改→部署流程

### 修改前端代码后

```bash
# 1. 编译前端
cd web
pnpm release
cd ..

# 2. 重新编译后端（必须！因为前端文件嵌入在后端）
go build -o memos.exe ./cmd/memos

# 3. 停止服务器（Windows）
netstat -ano | findstr :8081
taskkill //F //PID <PID>

# 4. 启动服务器
./memos.exe --mode dev --port 8081

# 5. 浏览器硬刷新（Ctrl+Shift+R）
```

### 修改后端代码后

```bash
# 1. 重新编译后端
go build -o memos.exe ./cmd/memos

# 2. 停止服务器
netstat -ano | findstr :8081
taskkill //F //PID <PID>

# 3. 启动服务器
./memos.exe --mode dev --port 8081
```

### 修改 Protocol Buffers 后

```bash
# 1. 重新生成代码
cd proto
buf generate
cd ..

# 2. 编译前端
cd web
pnpm release
cd ..

# 3. 编译后端
go build -o memos.exe ./cmd/memos

# 4. 重启服务器
```

## 常见问题

### Q: 为什么修改前端后必须重新编译后端？

A: 因为后端使用 `//go:embed` 在**编译时**将前端文件嵌入到可执行文件中。修改 `server/router/frontend/dist/` 目录下的文件不会影响已经编译好的 `memos.exe`。

### Q: 浏览器看不到最新的修改？

A: 尝试以下步骤：
1. 确认已经执行 `pnpm release` 重新编译前端
2. 确认已经重新编译后端 `go build -o memos.exe ./cmd/memos`
3. 确认已经重启服务器
4. 浏览器硬刷新（Ctrl+Shift+R）
5. 如果还不行，清除浏览器缓存

### Q: 如何确认前端文件是否正确嵌入？

A: 查看 `server/router/frontend/dist/` 目录，确认文件已更新：
```bash
ls -la server/router/frontend/dist/assets/
```

检查 HTML 文件中引用的 JS/CSS 文件名是否匹配。

### Q: 开发模式和生产模式有什么区别？

A:
- **dev 模式**: 启用更详细的日志，数据库文件为 `memos_dev.db`
- **prod 模式**: 优化的日志级别，数据库文件为 `memos_prod.db`

## 配置参数

### 环境变量

```bash
MEMOS_MODE=dev          # 运行模式: dev, prod, demo
MEMOS_PORT=8081         # HTTP 端口
MEMOS_DATA=./data       # 数据目录
MEMOS_DRIVER=sqlite     # 数据库驱动: sqlite, mysql, postgres
```

### 命令行参数

```bash
./memos.exe --mode dev --port 8081 --data ./data
```

## 数据库

### SQLite（默认）

数据库文件位置：
- 开发模式: `./memos_dev.db`
- 生产模式: `./memos_prod.db`

### 备份数据库

```bash
# 备份
cp memos_dev.db memos_dev.db.backup

# 恢复
cp memos_dev.db.backup memos_dev.db
```

## Git 工作流

### 回退未提交的修改

```bash
# 回退单个文件
git restore path/to/file

# 回退所有修改
git restore .

# 回退已 staged 的修改
git restore --staged path/to/file
```

### 查看修改

```bash
# 查看工作区修改
git status
git diff

# 查看已 staged 的修改
git diff --staged
```
