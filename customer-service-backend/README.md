# 客服服务 customer-service-backend

电商 AI 三方联调的 **AI 中枢**：接收用户消息，判断意图，编排对话，
需要业务数据就调 spzx 电商后端，需要知识就调知识库服务的 RAG 检索接口。

```
                       ┌──────────────────────────────┐
       用户 ──────────> │ 客服服务  customer-service     │ 18082
                       │ 意图规划 + 对话编排 + 槽位收集   │
                       └───────┬──────────────┬───────┘
                               │              │
                  task 轨道     │              │  knowledge 轨道
              查订单/物流/退款   │              │  RAG 知识检索
                               ▼              ▼
                    ┌────────────────────┐  ┌──────────────────────┐
                    │ spzx 电商后端        │  │ 知识库服务 8001       │
                    │ order 9207          │  │ LangGraph + Milvus    │
                    │ product 9205        │  └──────────────────────┘
                    └────────────────────┘
```

设计上的两条硬约束：

1. **不直连商城数据库**。所有订单/商品/物流数据都走 spzx 的内部 HTTP 接口，
   电商后端换实现时，改 `app/infrastructure/commerce_spzx.py` 即可。
2. **不自己实现检索**。知识类问题整段转发给知识库服务，RAG 挂了只会影响知识回答，不影响查订单。

---

## 一、目录结构

```
customer-service-backend
├── app
│   ├── api/                  FastAPI 入口、路由、依赖注入
│   │   ├── app.py              应用装配（lifespan 里装配引擎 + 建连接池）
│   │   └── routers/chat_router.py   POST /api/chat、GET /api/chat/history
│   ├── config/config.py      环境配置（pydantic-settings 读 .env）
│   ├── domain/               对话状态、消息、槽位等领域对象
│   ├── engine/               对话引擎：状态机 + 流程解释器
│   ├── planning/             意图识别、缺口澄清、计划校验
│   ├── prompts/              Jinja2 提示词模板（planning/clarify/knowledge/chitchat）
│   ├── infrastructure/       外部依赖封装
│   │   ├── commerce_spzx.py    ← spzx 电商后端适配器（订单/物流/SKU）
│   │   ├── http_client.py      全局 AsyncClient（注意：必须模块级创建）
│   │   ├── llm.py              OpenAI 兼容客户端
│   │   └── database.py         SQLAlchemy 异步引擎
│   ├── knowledge/            知识轨道：provider / planner / responder
│   │   └── provider.py         api.product / api.order / rag.default
│   ├── task/                 任务轨道：action 注册与执行
│   │   └── actions/custom/     lookup_order_status、lookup_logistics 等
│   ├── chitchat/             闲聊兜底
│   ├── models/               dialogue_states 表模型
│   ├── repository/           对话状态持久化
│   └── service/              对话服务编排
├── flow_config/user_flows.yml  槽位与话术流程（订单查询/物流/退款/欢迎引导）
├── main.py                     `python main.py` 启动（reload 模式）
├── requirements.txt
└── .env.example               配置模板，复制成 .env 使用
```

---

## 二、环境要求

| 依赖 | 要求 | 说明 |
|---|---|---|
| Python | 3.12 | 3.11/3.13 也可，依赖里有版本锁 |
| MySQL | 8.0 | 只需要一个 `customer_service` 库，存对话状态 |
| 大模型 | OpenAI 兼容接口 | 默认通义千问 `qwen-plus`（DashScope 兼容模式） |
| spzx 后端 | order 9207、product 9205 | 见 `../spzx-parent` |
| 知识库服务 | 8001 | 见 `../knowledge-service` |

### 初始化

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 建库（只需要一张表，首次启动会自动建表）
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS customer_service DEFAULT CHARSET utf8mb4;"

copy .env.example .env          # 然后填 LLM_API_KEY 和数据库密码
```

---

## 三、配置说明（.env）

| 配置 | 默认值 | 说明 |
|---|---|---|
| `LLM_MODEL` | `qwen-plus` | 任意 OpenAI 兼容模型名 |
| `LLM_BASE_URL` | DashScope 兼容地址 | 换 Kimi/DeepSeek 时改这里 |
| `LLM_API_KEY` | — | **不要提交到仓库**（已在 .gitignore） |
| `SPZX_ORDER_BASE_URL` | `http://127.0.0.1:9207` | spzx 订单服务 |
| `SPZX_PRODUCT_BASE_URL` | `http://127.0.0.1:9205` | spzx 商品服务 |
| `DATABASE_URL` | `mysql+aiomysql://...@127.0.0.1:3306/customer_service` | 对话状态库 |
| `APP_HOST` / `APP_PORT` | `127.0.0.1` / `18082` | |
| `RAG_SERVICE_URL` | `http://127.0.0.1:8001` | 知识库服务地址 |
| `RAG_SERVICE_TIMEOUT` | `120` | **必须给足**：RAG 单次 3~65s，给 60s 会偶发超时 |

---

## 四、启动

```bash
# 推荐（显式指定端口，避免与其它服务冲突）
.venv\Scripts\python.exe -m uvicorn app.api.app:app --host 127.0.0.1 --port 18082

# 或
.venv\Scripts\python.exe main.py
```

启动时会装配对话引擎并从 MySQL 加载历史状态，**约 5~10 秒**才可用。
探测：`GET http://127.0.0.1:18082/openapi.json` 返回 200 即就绪（`/` 没有路由，返回 404 是正常的）。

启动顺序：Nacos/MySQL/Redis/RabbitMQ → spzx-product → spzx-order → **本服务** → 知识库服务。
本服务最后启动也行，但 spzx 没起来时查订单只会回"暂时查不到"。

---

## 五、接口

### POST /api/chat

```json
{"sender_id": "u1", "text": "帮我查订单状态"}
```

带商品上下文时（知识轨道需要）：

```json
{"sender_id": "u1", "text": "这个有货吗",
 "object": {"type": "product", "id": "3", "title": "小米 红米Note10", "attributes": {}}}
```

响应：

```json
{"sender_id": "u1", "message_id": "...",
 "messages": [{"text": "订单SP202610260001当前状态是：商家正在备货，尚未发货。订单金额 ¥1999.00。商品：...", "object": null}]}
```

### GET /api/chat/history?sender_id=u1

返回该用户的历史对话（含"以上为历史消息"分隔）。

### 实测样例

```bash
curl --noproxy '*' -X POST http://127.0.0.1:18082/api/chat \
  -H "Content-Type: application/json" -d '{"sender_id":"u1","text":"帮我查订单状态"}'
curl --noproxy '*' -X POST http://127.0.0.1:18082/api/chat \
  -H "Content-Type: application/json" -d '{"sender_id":"u1","text":"SP202610260001"}'
# -> 订单SP202610260001当前状态是：商家正在备货，尚未发货。订单金额 ¥1999.00。...
```

知识类问题（走 RAG，约 15~60s）：

```bash
curl --noproxy '*' -X POST http://127.0.0.1:18082/api/chat \
  -H "Content-Type: application/json" -d '{"sender_id":"u1","text":"退货政策是怎么规定的"}'
```

---

## 六、与 spzx 的对接细节

`app/infrastructure/commerce_spzx.py` 只做三件事，全部是 GET：

| 客服侧函数 | 调用的 spzx 接口 | 鉴权 |
|---|---|---|
| `fetch_order(orderNo)` | `/orderInfo/inner/ai/{orderNo}` | 请求头 `from-source: inner` |
| `fetch_logistics(orderNo)` | `/orderInfo/inner/logistics/{orderNo}` | 同上 |
| `fetch_product(skuId)` | `/product/inner/ai/sku/{skuId}` | 同上 |

spzx 返回的是**为 AI 定制的聚合视图**（状态文案、脱敏手机号、可用库存都已算好），
这里只做字段重命名成客服内部统一的 dict，不做业务判断。任何异常都被吞掉返回 `None`，
由 action 层给"暂时查不到，请稍后再试"的话术 —— 保证 RAG 或订单服务宕机时对话不 500。

> `skuId` 必须是数字。传 `SKU10001` 这种旧格式会直接短路返回 `None`（spzx 的主键是自增 bigint）。

---

## 七、已知限制

1. **槽位不从首句抽取**：说"查订单 SP202610260001"仍会被追问一次订单号，需要再发一次订单号。
   当前为分轮填槽设计，可优化成首句正则/LLM 抽取。
2. **知识库内容是产品手册**（万用表、笔记本等），已额外灌入两份电商政策文档（退款/物流），
   所以问"退货政策"能命中；问具体商品参数则要看知识库里有没有对应文档。
3. **单轮延迟较高**：知识类问题要等 RAG（3~20s）+ 自身 LLM 改写，生产上应改流式。
4. **`app/infrastructure/http_client.py` 必须模块级创建客户端**：写成 `http_client = None` 再 init，
   其他模块 `from ... import http_client` 会在 import 时就把 `None` 绑死，之后赋值不生效，
   表现为所有业务查询静默失败。

---

## 八、常见问题

| 现象 | 处理 |
|---|---|
| 本地请求 502 | 系统代理劫持了 127.0.0.1。curl 加 `--noproxy '*'`，Python 里 `session.trust_env = False` |
| 启动报 `ValidationError` 缺字段 | `.env` 没建或少了必填项，对照 `.env.example` |
| 查订单一直"暂时查不到" | 先直连 `curl "http://127.0.0.1:9207/orderInfo/inner/ai/SP202610260001" -H "from-source: inner"`，再看 spzx 日志 |
| 知识问题回"暂时查不到" | 知识库服务 8001 没起，或 `RAG_SERVICE_TIMEOUT` 太小 |
| `'messages' must contain the word 'json'` | DashScope 限制：用 `response_format=json_object` 时 prompt 必须出现 "json"（已在 LLM 客户端按 response_format 分开缓存规避） |
