# AI Parts - Memos AI Service

统一的 AI 服务，提供标签生成、向量索引和语义搜索功能。

## 目录结构

```
ai_parts/
├── main.py                      # 主入口：FastAPI 应用
├── config.py                    # 配置管理
├── models.py                    # 数据模型（Pydantic）
├── core/                        # 核心功能模块
│   ├── __init__.py
│   ├── embeddings.py           # Jina 嵌入模型（文本 v3 + 图片 v4）
│   └── image_captioner_qwen.py # Qwen 视觉模型图片描述生成
├── services/                    # 业务逻辑层
│   ├── __init__.py
│   └── tag_service.py          # AI 标签生成服务
├── indexing/                    # 向量索引模块
│   ├── __init__.py
│   ├── memo_loader.py          # Memo → LlamaIndex 文档转换
│   └── index_manager.py        # 向量索引管理器（ChromaDB）
└── api/                         # API 路由
    ├── __init__.py
    ├── tags.py                 # 标签生成端点
    ├── indexing.py             # 索引管理端点
    └── search.py               # 语义搜索端点
```

## 快速开始

### 启动服务

```bash
# 方式 1：直接运行
python -m uvicorn ai_parts.main:app --host 0.0.0.0 --port 8001

# 方式 2：使用脚本
python ai_parts/main.py
```

### 检查服务状态

```bash
curl http://localhost:8001/health
```

## API 端点

### 基础端点

- `GET /` - 服务信息
- `GET /health` - 健康检查

### 标签生成（Tags API）

- `POST /api/v1/tags/generate` - 为 Memo 生成 AI 标签

**请求示例:**
```json
{
  "memo": {
    "name": "memos/abc123",
    "content": "这是一篇关于机器学习的笔记",
    "tags": ["AI"]
  },
  "user_all_tags": ["AI", "机器学习", "深度学习"],
  "max_tags": 5
}
```

### 索引管理（Indexing API）

- `GET /internal/index/status` - 获取索引状态
- `POST /internal/index/memo` - 索引/更新 Memo（异步）
- `DELETE /internal/index/memo/{memo_uid}` - 删除 Memo 索引
- `GET /internal/index/memo/{memo_uid}` - 查询 Memo 索引信息

**索引请求示例:**
```json
{
  "memo": {
    "name": "memos/abc123",
    "content": "内容",
    "attachments": [...]
  },
  "operation": "upsert"
}
```

### 语义搜索（Search API）

- `POST /internal/search` - 语义搜索 Memo

**搜索模式:**
- `text` - 纯文本语义搜索
- `image` - 纯图片语义搜索
- `hybrid` - 混合搜索（文本 + 图片）

**搜索请求示例:**
```json
{
  "query": "机器学习",
  "top_k": 10,
  "search_mode": "hybrid",
  "min_score": 0.3
}
```

**搜索响应示例:**
```json
{
  "query": "机器学习",
  "total": 3,
  "results": [
    {
      "memo_uid": "memos/abc123",
      "score": 0.85,
      "content": "关于机器学习的内容...",
      "metadata": {
        "creator": "users/1",
        "tags": "AI, 机器学习"
      }
    }
  ]
}
```

## 核心功能

### 1. AI 标签生成

使用 OpenAI 兼容的 API（默认 gpt-4.1-mini）为 Memo 生成标签：
- 分析正文内容
- 分析附件信息（文本、图片）
- 支持图片内容理解（vision）
- 优先复用用户已有标签
- 支持中英文混合

### 2. 多模态向量索引

- **文本索引**: 使用 Jina Embeddings v3
- **图片索引**: 使用 Jina Embeddings v4
- **存储**: ChromaDB 持久化存储
- **增量更新**: 支持添加、更新、删除单个 Memo
- **异步处理**: 图片描述生成使用并发处理

### 3. 语义搜索

- **混合搜索**: 同时搜索文本和图片内容
- **分数过滤**: 支持最低相似度阈值
- **结果去重**: 同一 Memo 只返回最高分结果
- **灵活模式**: 支持纯文本、纯图片或混合搜索

## 配置

环境变量配置（在 `config.py` 中定义）：

```bash
# OpenAI 兼容 API（用于标签生成）
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxx
TAG_GENERATION_MODEL=gpt-4.1-mini

# 阿里云 DashScope（用于图片描述）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=sk-xxx
IMAGE_CAPTION_MODEL=qwen-vl-max

# Jina Embeddings
JINA_API_KEY=jina_xxx
JINA_TEXT_MODEL=jina-embeddings-v3
JINA_IMAGE_MODEL=jina-clip-v2

# 服务配置
AI_SERVICE_HOST=0.0.0.0
AI_SERVICE_PORT=8001
INDEX_BASE_DIR=.memo_indexes/chroma
```

## 测试

运行测试脚本：

```bash
# 测试搜索功能
python dev_tests/test_search_api.py

# 测试索引服务
python dev_tests/test_index_service.py

# 测试 Memo 加载
python dev_tests/test_memo_loader.py
```

## 技术栈

- **Web 框架**: FastAPI
- **向量数据库**: ChromaDB
- **索引框架**: LlamaIndex
- **嵌入模型**: Jina Embeddings v3/v4
- **视觉模型**: Qwen VL / OpenAI Vision
- **异步处理**: asyncio + BackgroundTasks

## 性能优化

1. **并发图片处理**: 使用 `asyncio.gather()` 并发生成图片描述
2. **后台任务**: 索引操作使用 FastAPI BackgroundTasks，立即返回
3. **持久化存储**: ChromaDB 自动持久化，重启后快速恢复
4. **增量更新**: 只更新变化的 Memo，避免全量重建

## 架构设计

### 分层架构

1. **API 层** (`api/`): 处理 HTTP 请求，参数验证
2. **服务层** (`services/`): 业务逻辑，标签生成
3. **核心层** (`core/`): 基础功能，嵌入、图片描述
4. **索引层** (`indexing/`): 向量索引管理

### 依赖注入

索引管理器通过依赖注入模式传递到各个路由模块：

```python
# main.py
manager = get_index_manager()
indexing.set_index_manager(manager)
search.set_index_manager(manager)
```

### 模块化设计

每个 API 路由是独立的 FastAPI Router，便于：
- 独立测试
- 功能扩展
- 代码维护

## 开发指南

### 添加新的 API 端点

1. 在对应的路由文件中添加端点（`api/tags.py`, `api/indexing.py`, `api/search.py`）
2. 如果需要新的路由分组，创建新文件如 `api/new_feature.py`
3. 在 `api/__init__.py` 中导出
4. 在 `main.py` 中注册路由：`app.include_router(new_feature.router)`

### 添加新的业务逻辑

1. 在 `services/` 目录创建新服务文件
2. 实现业务逻辑函数
3. 在 API 路由中调用

### 扩展核心功能

1. 在 `core/` 目录添加新模块
2. 保持模块独立性和可测试性
3. 通过配置管理依赖项

## 版本历史

- **v1.0.0** (2025-11-21)
  - 完整的目录结构重构
  - 模块化 API 路由设计
  - 统一的服务入口
  - 支持标签生成、索引管理、语义搜索

## License

MIT
