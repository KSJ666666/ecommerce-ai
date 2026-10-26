# 知识库服务 (Knowledge Service)

基于 RAG（检索增强生成）的智能知识库问答系统。支持文档智能导入、混合向量检索、多路召回融合、智能重排序与流式问答，适用于产品手册、技术文档、企业知识库等场景。

> **在电商 AI 三方联调中的角色**：作为「知识轨道」的知识源。
> 客服服务（`../customer-service-backend`）遇到政策、规则、文档类问题时不自己检索，
> 而是把问题整段 POST 到本服务 `8001/query`，拿到答案后再用自己的话术改写。
> 查订单/物流这种结构化数据不走这里，直接走 spzx 电商后端。

---

## 一、功能特性

| 模块 | 描述 |
|------|------|
| 文档智能导入 | 支持 PDF/Markdown 文件上传，自动解析、切分、向量化、入库 |
| 混合向量检索 | 稠密向量 + 稀疏向量（BM25）混合检索 |
| 多路召回融合 | 向量检索 + HyDE + Web 搜索，RRF 融合 |
| 智能重排序 | Reranker 模型重排序，断崖检测动态截断 |
| 流式问答 | SSE 实时推送，逐 token 输出答案 |
| 会话历史管理 | MongoDB 存储对话历史，支持上下文连续对话 |

---

## 二、系统架构

两个独立的 FastAPI 应用，分别负责导入与查询：

```
┌─────────────────────────────────────────────────────┐
│                  前端层 (knowledge/front)             │
│    导入界面 (import.html)  │  聊天界面 (chat.html)    │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                   API 层 (knowledge/api)              │
│  导入服务 :8000 (import_router.py)  POST /upload      │
│                                   GET  /status/{id}  │
│  查询服务 :8001 (query_router.py)   POST /query       │
│                                   GET  /stream/{id}  │
│                                   GET  /history/{id} │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Processor 层 (LangGraph 有状态图)         │
│  import_processor（导入流程） │ query_processor（查询流程）│
└─────────────────────────────────────────────────────┘
```

### 文档导入流水线

```
文件上传 → PDF解析(MineRU) → MD切分 → 图片提取&摘要 → 商品名识别 → 向量化(BGE-M3/OpenAI) → 入库(Milvus)
```

### 检索增强生成（RAG）流水线

```
用户问题 → 商品名确认 → 多路召回(向量+HyDE+Web) → RRF融合 → Reranker重排序 → LLM生成 → SSE流式输出
```

---

## 三、技术选型

| 类别 | 技术方案 | 说明 |
|------|----------|------|
| 后端框架 | FastAPI + Uvicorn | 异步高性能 HTTP 服务 |
| 工作流引擎 | LangGraph | 有状态图编排框架 |
| 大语言模型 | 阿里云 DashScope (Qwen) | qwen-flash / qwen3-vl-flash |
| 向量嵌入 | OpenAI API (text-embedding-v4) + BGE-M3 | 1536维 / 1024维+稀疏 |
| 重排序模型 | BGE-Reranker-Large | 本地部署（FlagEmbedding） |
| 向量数据库 | Milvus | 混合检索（稠密+稀疏） |
| 文档数据库 | MongoDB | 对话历史存储 |
| 对象存储 | MinIO | 文件与图片存储 |
| PDF 解析 | MineRU | PDF 转 Markdown |
| 前端 | HTML5 + JS | 无框架，轻量实现 |

---

## 四、项目结构

```
knowledge-service/
├── main.py                         # 启动入口：python main.py [query|import]
├── docker-compose.yml              # etcd + MinIO + Milvus + Attu + MongoDB
├── tests/                          # 集成测试
└── knowledge/
    ├── .env / .env.example         # 环境变量配置（.env 不提交）
    ├── requirements.txt            # Python 依赖
    ├── api/                        # API 路由层
    │   ├── import_router.py          导入服务 8000
    │   └── query_router.py           查询服务 8001
    ├── core/                       # 依赖装配（deps）与路径管理（paths）
    ├── front/                      # 轻量前端页面
    │   ├── import.html               文档导入界面
    │   └── chat.html                 聊天界面
    ├── processor/
    │   ├── import_processor/       # 文档导入流程（LangGraph）
    │   │   ├── main_graph.py         导入流程图定义
    │   │   ├── config.py / state.py  配置与状态类型
    │   │   ├── base.py               节点基类（统一接口/日志/异常）
    │   │   ├── exceptions.py         自定义异常
    │   │   └── nodes/                entry / pdf_to_md / document_split /
    │   │                             md_to_img / item_name_recognition /
    │   │                             embedding_chunks / import_milvus
    │   └── query_processor/        # 查询处理流程（LangGraph）
    │       ├── main_graph.py         查询流程图定义
    │       ├── config.py / state.py  配置与状态类型
    │       └── nodes/                hybrid_vector_search / hyde_vector_search /
    │                                 web_mcp_search / rrf_merge / reranker /
    │                                 item_name_confirmed / answer_output
    ├── prompts/                    # 导入/查询提示词
    ├── schema/                     # Pydantic 数据模型（query / upload）
    ├── service/                    # 业务服务层（query_service / upload_service）
    ├── utils/                      # 工具层
    │   ├── embedding_util / milvus_util / markdown_util
    │   ├── mongo_history_util / sse_util / task_util
    │   └── client/                   ai_clients / storage_clients
    └── test/                       # 导入/查询/阈值调优测试脚本
```

---

## 五、快速开始

### 环境要求

| 依赖 | 要求 | 说明 |
|---|---|---|
| Python | 3.11（3.10~3.12 均可） | 3.13 对 mineru/pymilvus 支持不好，别用 |
| GPU | 建议 CUDA 可用 | BGE-M3 与 BGE-Reranker 默认 `cuda:0`；无卡把 `BGE_DEVICE`/`BGE_RERANKER_DEVICE` 改 `cpu`（会慢很多） |
| Milvus | 19530 | 稠密+稀疏混合检索，Milvus Lite 不支持，必须起服务 |
| MongoDB | 27017 | 存对话历史，挂了不影响检索主流程 |
| MinIO | 9000 | 存上传的原始文档与图片 |
| 大模型 | OpenAI 兼容接口 | 默认 DashScope `qwen-flash` |

中间件用目录下的 `docker-compose.yml` 一把起（etcd + MinIO + Milvus + Attu + MongoDB）：

```bash
docker compose up -d
# 等 Milvus 健康检查通过（约 90 秒）
curl http://127.0.0.1:9091/healthz
```

### 安装依赖

```bash
# 推荐用 conda 单独建环境，避免和别处的 pymilvus/torch 打架
conda create -n knowledge-service python=3.11 -y
conda activate knowledge-service
pip install -r knowledge/requirements.txt
```

### 配置环境变量

配置项在 `knowledge/.env`（**已被 .gitignore 排除，不要提交**），模板见 `knowledge/.env.example`。

| 配置 | 示例 | 注意 |
|---|---|---|
| `OPENAI_API_KEY` / `OPENAI_API_BASE` | DashScope 兼容地址 | 要和 `LLM_DEFAULT_MODEL` 匹配 |
| `LLM_DEFAULT_MODEL` | `qwen-flash` | 换模型注意「json」限制，见常见问题 |
| `BGE_M3_PATH` | `D:/developtools/bge-m3` | 本机目录名里是 U+2011 非断连字符，照抄时别手打成普通减号 |
| `BGE_RERANKER_LARGE` | `...\bge-reranker-large` | |
| `BGE_DEVICE` | `cuda:0` / `cpu` | 无卡改 `cpu` |
| `MILVUS_URL` | `http://127.0.0.1:19530` | |
| `CHUNKS_COLLECTION` / `ITEM_NAME_COLLECTION` | `kb_chunks_v1` / `kb_item_names_v1` | 换库时改这里 |
| `MONGO_URL` | `mongodb://localhost:27017` | |
| `MINIO_ENDPOINT` | `localhost:9000` | 桶 `knowledge-base-v1` |

### 启动服务

两个 FastAPI 应用，按需启动：

```bash
cd knowledge-service

# 方式一：统一入口
python main.py            # 查询服务 8001（联调时用这个）
python main.py import     # 导入服务 8000（往知识库灌文档时才用）

# 方式二：直接 uvicorn
python -m uvicorn knowledge.api.query_router:create_app --factory --host 127.0.0.1 --port 8001
python -m uvicorn knowledge.api.import_router:create_app --factory --host 127.0.0.1 --port 8000
```

启动要加载 BGE 模型和 YAML 流程，**约 5~10 秒**才可用；探测 `GET http://127.0.0.1:8001/` 返回
`{"flag":"success"}` 即就绪。

> **不要同时开 8000 和 8001**：两者都要加载 BGE-M3（约 2GB 显存），同时持有会 `Segmentation fault`。
> 正确顺序：停 8001 → 导入 → 完成后重开 8001。
> 另外 8000 常被 Attu（Milvus 控制台）占用，起导入服务前先确认端口。

---

## 六、接口

### 查询服务（8001）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 健康检查，返回 `{"flag":"success"}` |
| POST | `/query` | 知识问答，`is_stream=false` 同步返回，`true` 返回 task_id 走流式 |
| GET | `/stream/{task_id}` | SSE 流式拉取答案 |
| GET | `/history/{session_id}` | 会话历史 |

### 导入服务（8000）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 健康检查 |
| POST | `/upload` | 上传 PDF/Markdown 文档，返回 task_id |
| GET | `/status/{task_id}` | 查询导入进度 |

---

## 七、与客服服务联调

客服服务（`../customer-service-backend`）的知识轨道会把用户问题整段转发到本服务的 `POST /query`：

```bash
curl --noproxy '*' -X POST http://127.0.0.1:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"退货政策是怎么规定的","is_stream":false}'
# -> {"message":"查询请求已经处理完了","session_id":"...","answer":"根据退款与退货政策…"}
```

首次查询要预热模型和 Milvus 连接，约 20~40s；之后单次 3~20s。
客服侧超时 `RAG_SERVICE_TIMEOUT` 必须 ≥120，否则表现为"客服从不报错但总说查不到"。

已入库的电商政策文档见根目录 `_kb_docs/`（退款与退货政策、物流与配送政策），
需要重新导入时走 8000 的 `/upload` 接口。

---

## 八、核心设计

### LangGraph 工作流

导入与查询流程均采用 **LangGraph 有状态图** 编排，通过 `BaseNode` 基类统一节点接口：

- **状态管理**：`TypedDict` 定义全流程传递的数据结构（`state.py`）
- **节点基类**：`BaseNode` 提供 `__call__` 统一入口，自动处理日志、任务追踪和异常包装
- **PDF 解析节点**：`PdfToMdNode` 调用 MinerU 子进程将 PDF 转为 Markdown，支持实时日志输出
- **配置中心**：`config.py` 集中管理切片策略、模型参数、外部服务连接等配置

### 依赖清单

```
fastapi / uvicorn / python-multipart   # Web 层（文件上传必需）
langchain-openai / langgraph           # LLM 与工作流编排
openai-agents / grandalf               # Agent SDK 与图布局渲染
pymilvus[model] / sentence-transformers # 向量库客户端与嵌入模型
FlagEmbedding                          # BGE 重排序
minio / pymongo                        # 对象存储 / 文档库
mineru[all] / pypdf                    # PDF 解析
```

---

## 九、常见问题

| 现象 | 处理 |
|---|---|
| `'messages' must contain the word 'json'` | DashScope 限制：`response_format=json_object` 时 prompt 里必须出现 "json"。本项目已按 response_format 分开缓存客户端规避 |
| 检索命中但回答"暂无" | `rrf_merge_node` 存的是 `[(chunk, score)]` 元组，`reranker_node` 若按 dict 判断会全部跳过 → 重排输入为 0。已兼容元组 |
| 问政策类问题一律"无法识别产品名称" | 商品名提取提示词原先要求"无法确定就返回空"，政策问题天然没有商品名，已放开 |
| 导入后同一文档命中被降级成反问 | `kb_item_names_v1` 里同一 item_name 写了 2 份，分数差为 0 触发多候选分支，需清理重复行 |
| 启动报 `No module named knowledge.schema.query_schema` | 依赖文件缺失，确认 `knowledge/schema/query_schema.py` 存在 |
| RAG 特别慢（60s+） | Milvus/Mongo 没起，客户端在重连。`docker compose ps` 看三个容器是否 healthy |
| 启动报 `Segmentation fault` | 8000 与 8001 同时加载 BGE-M3，串行启动 |
| 本地 curl 502 | 系统代理劫持，加 `--noproxy '*'` |

---

## License

MIT
