# Memos REST API 测试工具

这是一个用于测试 Memos MemoService REST API 的 Python 演示脚本。

## 前置要求

- Python 3.7+
- Memos 服务运行中（默认地址：http://localhost:8081）

## 安装依赖

```bash
pip install -r requirements.txt
```

或者直接安装：

```bash
pip install requests
```

## 使用方法

### 1. 启动 Memos 服务

确保 Memos 服务正在运行：

```bash
# 开发模式
go run ./cmd/memos --mode dev --port 8081
```

### 2. 运行测试脚本

```bash
python test_memo_service.py
```

### 3. 自定义配置

编辑 `test_memo_service.py` 中的配置：

```python
# 修改基础 URL
BASE_URL = "http://localhost:8081"

# 添加认证 Token（可选）
AUTH_TOKEN = "your-token-here"
```

## 测试内容

脚本包含以下测试场景：

### 基础查询
1. **列出所有备忘录**（匿名访问，仅返回 PUBLIC 备忘录）
2. **分页查询**（page_size 参数）
3. **获取单个备忘录**（通过 ID）

### 过滤器测试（CEL 表达式）
4. **内容搜索**: `content.contains("test")`
5. **按可见性过滤**: `visibility == "PUBLIC"`
6. **按置顶状态过滤**: `pinned == true`
7. **按代码属性过滤**: `has_code == true`
8. **时间范围过滤**: `created_ts > {timestamp}`
9. **使用 now() 函数**: `created_ts > now() - 7 * 24 * 3600`
10. **组合条件**: `visibility == "PUBLIC" && pinned == false`

### 排序测试
11. **自定义排序**: `order_by="create_time asc"`

### 错误处理
12. **无效过滤器**（测试错误响应）
13. **无认证创建备忘录**（测试权限控制）

## 支持的 Filter 字段

| 字段 | 类型 | 示例 |
|------|------|------|
| `content` | string | `content.contains("关键词")` |
| `creator_id` | int | `creator_id == 1` |
| `created_ts` | timestamp | `created_ts > now() - 86400` |
| `updated_ts` | timestamp | `updated_ts > 1234567890` |
| `pinned` | bool | `pinned == true` |
| `visibility` | string | `visibility == "PUBLIC"` |
| `tags` | list | `"工作" in tags` |
| `has_task_list` | bool | `has_task_list == true` |
| `has_link` | bool | `has_link == true` |
| `has_code` | bool | `has_code == true` |
| `has_incomplete_tasks` | bool | `has_incomplete_tasks == true` |

## 输出示例

```
Memos REST API Demo
============================================================

============================================================
Test 1: List All Memos (Anonymous)
============================================================

[List All Memos]
Status Code: 200
Response: {
  "memos": [
    {
      "name": "memos/123",
      "content": "这是一个测试备忘录",
      "visibility": "PUBLIC",
      "createTime": "2024-01-01T00:00:00Z",
      ...
    }
  ]
}

Total memos returned: 5
First memo preview:
  - Name: memos/123
  - Visibility: PUBLIC
  - Content: 这是一个测试备忘录...
```

## 扩展使用

### 添加认证测试

如果需要测试需要认证的接口，设置 `AUTH_TOKEN`：

```python
client = MemoServiceClient(BASE_URL, AUTH_TOKEN="your-jwt-token")
```

### 添加更多测试

参考 `MemoServiceClient` 类，可以轻松添加更多测试：

```python
# 自定义过滤器测试
status, data = client.list_memos(
    filter_expr='visibility == "PRIVATE" && has_task_list == true',
    order_by="update_time desc",
    page_size=10
)
```

## API 文档参考

- **列出备忘录**: `GET /api/v1/memos`
- **获取单个备忘录**: `GET /api/v1/memos/{id}`
- **创建备忘录**: `POST /api/v1/memos`（需要认证）

详细 API 定义请查看：`proto/api/v1/memo_service.proto`

## 故障排除

### 连接失败

确保 Memos 服务正在运行：

```bash
curl http://localhost:8081/api/v1/memos
```

### 无数据返回

匿名访问仅能看到 PUBLIC 备忘录。如果没有公开备忘录，需要：
1. 创建一些 PUBLIC 可见性的备忘录
2. 或者使用认证 token

### Filter 错误

确保 filter 表达式语法正确，参考 CEL 表达式规范。
