# UTF-8 修复指南

## 问题描述

当备忘录内容包含无效的 UTF-8 字符序列时，会导致 gRPC 编码错误：

```
ERROR: [core] [Server #1]grpc: server failed to encode response:
rpc error: code = Internal desc = grpc: error while marshaling:
string field contains invalid UTF-8
```

这会导致：
- 无法保存新的备忘录
- 无法查询包含无效数据的备忘录
- 整个 API 可能受影响

## 解决方案

### 1. 代码层面修复（已完成）

已在以下位置添加 UTF-8 清理：
- `internal/util/util.go` - 添加 `SanitizeUTF8()` 函数
- `server/router/api/v1/memo_service.go` - CreateMemo 和 UpdateMemo 中应用清理

**重启服务后，新创建或更新的备忘录会自动清理无效 UTF-8。**

### 2. 数据库修复（清理已存在的无效数据）

#### 方法 A：使用修复脚本（推荐）

**快速修复（默认 SQLite）：**

```bash
cd dev_tests
go run fix_utf8.go
```

**先检查但不修改（Dry Run）：**

```bash
go run fix_utf8.go --dry-run
```

**指定数据目录：**

```bash
go run fix_utf8.go --data-dir C:\path\to\your\data
```

**使用 MySQL：**

```bash
go run fix_utf8.go --driver mysql --dsn "user:password@tcp(localhost:3306)/memos"
```

**使用 PostgreSQL：**

```bash
go run fix_utf8.go --driver postgres --dsn "postgres://user:password@localhost:5432/memos?sslmode=disable"
```

#### 方法 B：手动 SQL 修复

如果你熟悉 SQL，也可以手动修复：

**SQLite：**

```sql
-- 1. 先查找有问题的备忘录
SELECT id, uid, length(content) as len
FROM memo
WHERE content != CAST(content AS TEXT);

-- 2. 备份数据库
-- cp ~/.memos/memos_prod.db ~/.memos/memos_prod.db.backup

-- 3. 删除有问题的备忘录（谨慎操作！）
DELETE FROM memo WHERE id = <问题ID>;
```

**注意：** 手动 SQL 方法可能导致数据丢失，建议使用修复脚本。

## 重新启动服务

修复数据库后，重启 Memos 服务：

```bash
# 停止当前服务 (Ctrl+C)

# 重新启动
go run ./cmd/memos --mode dev --port 8081
```

## 测试验证

### 1. 运行 REST API 测试

```bash
cd dev_tests
python test_memo_service.py
```

应该能正常查询所有备忘录，不再出现 gRPC 错误。

### 2. 创建新备忘录测试

尝试创建包含特殊字符的备忘录，验证自动清理功能。

## 预防措施

1. **代码已自动清理** - 所有新建和更新的备忘录会自动清理无效 UTF-8
2. **定期检查** - 可以定期运行 `fix_utf8.go --dry-run` 检查数据库健康状态
3. **数据备份** - 建议定期备份数据库

## 常见问题

### Q: 修复脚本会丢失数据吗？

A: 不会。脚本只会将无效的 UTF-8 字节序列替换为 Unicode 替换字符（�），不会删除备忘录。

### Q: 如何知道哪些备忘录被修复了？

A: 运行脚本时会输出详细日志，包括每个被修复的备忘录的 UID 和 ID。

### Q: 可以撤销修复吗？

A: 修复前建议备份数据库：
```bash
# Windows
copy "%USERPROFILE%\.memos\memos_prod.db" "%USERPROFILE%\.memos\memos_prod.db.backup"

# Linux/Mac
cp ~/.memos/memos_prod.db ~/.memos/memos_prod.db.backup
```

### Q: 为什么会出现无效 UTF-8？

可能原因：
- 从其他编码（如 GBK、Latin1）复制粘贴文本
- 二进制数据意外插入
- 文件编码转换错误
- 某些旧版本的客户端输入

### Q: 修复后还是有问题怎么办？

1. 检查所有备忘录是否都已修复：
   ```bash
   go run fix_utf8.go --dry-run
   ```

2. 查看服务器日志，确认具体错误

3. 如果问题持续，可能需要重建相关索引或缓存

## 技术细节

### UTF-8 验证原理

Go 的 `utf8.ValidString()` 检查字符串是否为有效 UTF-8：
- 每个字节序列必须符合 UTF-8 编码规则
- 不允许过长编码
- 不允许代理对（surrogate pairs）

### 清理策略

当发现无效序列时：
```go
r, size := utf8.DecodeRuneInString(s)
if r == utf8.RuneError && size == 1 {
    // 替换为 Unicode 替换字符 U+FFFD (�)
    sb.WriteRune(utf8.RuneError)
}
```

这样可以保留大部分原始内容，只替换真正无效的字节。
