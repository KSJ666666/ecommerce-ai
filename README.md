# 电商 AI 智能客服联调系统

一套把「电商业务后端」「智能客服」「知识库问答」三个独立服务串成一条完整链路的联调工程。
用户在对话框里用自然语言提问，客服中枢判断意图后，要么去电商后端查结构化数据（订单/物流/商品），
要么去知识库服务做 RAG 检索（政策/规则/文档），最后用自己的话术把答案说回去。

先看一段真实对话，感受这条链路在做什么：

```
用户：帮我查订单状态
客服：请告诉我你的订单号。
用户：SP202610260001
客服：订单SP202610260001当前状态是：商家正在备货，尚未发货。订单金额 ¥1999.00。
      商品：小米 红米Note10 5G手机 红色 + 8G。

用户：退货政策是怎么规定的
客服：（转知识库 RAG 检索，约 15~60s）根据退款与退货政策，……
```

---

## 快速开始

> 前提：中间件（Nacos/MySQL/Redis/RabbitMQ + Milvus 全家桶）已就绪，见「环境要求」。

```bash
# 1. 起向量库等容器（Milvus / MinIO / MongoDB / etcd / Attu）
docker compose up -d

# 2. 导入联调演示订单（幂等，可反复执行）
mysql -uroot -p --default-character-set=utf8mb4 < spzx-parent/sql/ai_demo_orders.sql

# 3. 一键拉起四个服务（Windows）
start_all.bat

# 4. 自检
python verify_e2e.py            # 端口 + 健康接口，秒级
python verify_e2e.py --full     # 含端到端对话，约 40~90s
```

不想用脚本，就按「启动顺序」一节手动逐个拉起。

---

## 系统架构

```
                         ┌──────────────────────────────┐
        用户 ──────────→ │ 客服服务 customer-service     │ 18082
                         │ AI 中枢：意图规划 + 对话编排    │
                         └───────┬──────────────┬───────┘
                                 │              │
              task 轨道           │              │  knowledge 轨道
        查订单 / 物流 / 商品       │              │  RAG 知识检索
                                 ▼              ▼
                ┌──────────────────────┐  ┌──────────────────────┐
                │ 电商业务后端 spzx      │  │ 知识库服务            │ 8001 查询
                │ Spring Cloud 微服务    │  │ LangGraph + Milvus    │ 8000 导入
                │ order 9207            │  └──────────┬───────────┘
                │ product 9205          │             │
                └──────────┬───────────┘   Milvus 19530 / Mongo 27017 / MinIO 9000
                           │
        Nacos 8848 / MySQL 3306 / Redis 6379 / RabbitMQ 5672
```

### 三条设计硬约束

1. **客服不直连数据库**。订单/商品/物流数据全部走 spzx 的内部 HTTP 接口
   （请求头带 `from-source: inner`）。电商后端换实现时，客服侧只改一个适配器文件。
2. **客服不自己实现检索**。知识类问题整段转发给知识库服务，RAG 挂了只影响知识回答，不影响查订单。
3. **三方只有 HTTP 依赖**。任一方宕机都能各自降级——查不到就说"暂时查不到"，绝不抛 500。

---

## 三个服务

| 目录 | 角色 | 技术栈 | 端口 |
|---|---|---|---|
| `spzx-parent/` | 电商业务基座（商品/订单/购物车/支付/用户） | Spring Boot 3 + Spring Cloud + MyBatis-Plus + Nacos | 9205 / 9207 |
| `customer-service-backend/` | 智能客服，AI 中枢与对话编排 | Python 3.12 + FastAPI + LangGraph | 18082 |
| `knowledge-service/` | 知识库服务，RAG 知识问答 | Python 3.11 + FastAPI + LangGraph + Milvus | 8001 / 8000 |

每个目录都有自己的 `README.md`，写明各自的结构、环境、启动与排错。

### 数据怎么流

| 用户意图 | 走哪条轨道 | 打到哪 |
|---|---|---|
| 查订单状态 / 查物流 / 查商品 | task 轨道 | spzx 内部聚合接口 |
| 退货政策 / 配送规则等文档类问题 | knowledge 轨道 | 知识库服务 `8001/query` |
| 闲聊 / 兜底 | 本地 | 客服自身 LLM |

客服调 spzx 只走三个聚合接口（详见 `spzx-parent/README.md`）：

| 客服侧函数 | spzx 接口 | 说明 |
|---|---|---|
| `fetch_order` | `GET /orderInfo/inner/ai/{orderNo}` | 订单聚合视图 |
| `fetch_logistics` | `GET /orderInfo/inner/logistics/{orderNo}` | 物流状态 |
| `fetch_product` | `GET /product/inner/ai/sku/{skuId}` | SKU 聚合视图 |

---

## 环境要求

| 依赖 | 版本 | 用途 | 必需 |
|---|---|---|---|
| JDK | 17+（21 最佳） | 构建运行 spzx | ✅ |
| Maven | 3.6+ | 打包 spzx | ✅ |
| MySQL | 8.0 | spzx 各业务库 + `customer_service` 会话库 | ✅ |
| Redis | 6/7（密码 `123456`） | spzx 购物车/防重令牌/缓存 | ✅ |
| RabbitMQ | 3.x + 延迟消息插件 | 超时未支付自动取消订单 | ✅ |
| Nacos | 2.x | spzx 注册中心 + 配置中心 | ✅ |
| Python | 3.12（客服）/ 3.11（知识库） | 两个 Python 服务 | ✅ |
| Milvus / MongoDB / MinIO | — | 知识库服务的向量库/会话/文件存储 | 仅知识问答需要 |
| GPU | CUDA 可用 | BGE-M3 与 Reranker 推理 | 建议（无卡改 `BGE_DEVICE=cpu`） |

### 中间件准备

```bash
# 知识库服务用到的容器：Milvus + MinIO + MongoDB + etcd + Attu
docker compose up -d
curl http://127.0.0.1:9091/healthz      # 期望 200，首次约 90 秒

# Nacos / MySQL / Redis / RabbitMQ 用本机已有环境启动即可，检查：
#   8848 Nacos 控制台   3306 MySQL   6379 Redis   5672 RabbitMQ
```

spzx 的数据源、Redis 密码、RabbitMQ 账号都在 **Nacos 的 `spzx-xxx-dev.yml`** 里，不在代码里；
换机器部署要先把这些配置搬过去（见 `spzx-parent/README.md`）。

### 数据库与演示数据

```bash
# spzx 五个业务库 + 客服会话库
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS customer_service DEFAULT CHARSET utf8mb4;"

# 联调演示订单：4 条可读订单号，覆盖 待付款/待发货/已发货/已完成
mysql -uroot -p --default-character-set=utf8mb4 < spzx-parent/sql/ai_demo_orders.sql
```

> 为什么要造演示订单：真实下单的 `order_no` 是 32 位 UUID，让用户在对话框里手打不现实。
> 脚本幂等，得到 `SP202610260001`（待发货）、`…0002`（已发货）、`…0003`（已完成）、`…0004`（待付款）。

---

## 启动顺序

| # | 服务 | 命令 | 就绪判断 |
|---|---|---|---|
| 0 | 中间件 | `docker compose up -d` + Nacos/MySQL/Redis/RabbitMQ | `docker ps`、8848 控制台 |
| 1 | spzx-product | `java -jar spzx-modules/spzx-product/target/spzx-product.jar --server.port=9205` | 9205 可连 |
| 2 | spzx-order | `java -jar spzx-modules/spzx-order/target/spzx-order.jar --server.port=9207` | 9207 可连 |
| 3 | 客服服务 | `.venv\Scripts\python.exe -m uvicorn app.api.app:app --host 127.0.0.1 --port 18082` | `GET /openapi.json` 200 |
| 4 | 知识库服务 | `python -m uvicorn knowledge.api.query_router:create_app --factory --host 127.0.0.1 --port 8001` | `GET /` 返回 `{"flag":"success"}` |

- 首次运行 spzx 需先打包：`mvn -DskipTests -pl spzx-modules/spzx-order,spzx-modules/spzx-product -am package`
- Windows 可直接双击 **`start_all.bat`** 一键拉起；脚本顶部可用环境变量覆盖
  `SPZX_JAVA_HOME`（JDK 17+）、`CS_PY`（客服虚拟环境 python）、`KB_PY`（知识库 python）、`MVN`
- Java 服务启动约 25~40 秒（要连 Nacos 拉配置），知识库服务约 30 秒（加载 BGE 模型），别急着发请求

---

## 验证

```bash
pip install requests
python verify_e2e.py            # 端口 + 健康接口，秒级
python verify_e2e.py --full     # 端到端对话，约 40~90s
```

`--full` 会依次验证：客服→spzx 查订单（两轮填槽）、客服→spzx 查物流、客服→知识库 RAG 问答。

### 手工验证

```bash
# 1. 直连 spzx 订单
curl "http://127.0.0.1:9207/orderInfo/inner/ai/SP202610260001" -H "from-source: inner"

# 2. 直连 spzx 商品
curl "http://127.0.0.1:9205/product/inner/ai/sku/3" -H "from-source: inner"

# 3. 知识库服务（用已入库的真实文档提问）
curl -X POST http://127.0.0.1:8001/query -H "Content-Type: application/json" \
  -d '{"query":"退货政策是怎么规定的","is_stream":false}'

# 4. 客服 -> spzx（两轮填槽）
curl -X POST http://127.0.0.1:18082/api/chat -H "Content-Type: application/json" \
  -d '{"sender_id":"u1","text":"帮我查订单状态"}'
curl -X POST http://127.0.0.1:18082/api/chat -H "Content-Type: application/json" \
  -d '{"sender_id":"u1","text":"SP202610260001"}'

# 5. 客服 -> 知识库服务（政策类问题）
curl -X POST http://127.0.0.1:18082/api/chat -H "Content-Type: application/json" \
  -d '{"sender_id":"u1","text":"退货政策是怎么规定的"}'
```

> Windows 上如果配了系统代理，curl 要加 `--noproxy '*'`，否则 127.0.0.1 会被代理劫持成 502。

---

## 端口速查

| 端口 | 服务 |
|---|---|
| 8848 | Nacos |
| 3306 | MySQL |
| 6379 | Redis |
| 5672 / 15672 | RabbitMQ |
| 9205 | spzx-product |
| 9207 | spzx-order |
| 8080 | spzx-gateway（跑完整购物链路时才需要） |
| 9200 / 9201 / 9206 / 9209 / 9210 | spzx-auth / system / user / cart / payment |
| 18082 | 客服服务 |
| 8001 / 8000 | 知识库服务（查询 / 导入，8000 常被 Attu 占用） |
| 19530 / 27017 / 9000 | Milvus / MongoDB / MinIO |

---

## 目录结构

```
电商AI三方联调
├── spzx-parent/                  Java 电商后端（Spring Cloud）
│   ├── spzx-modules/spzx-order     订单/物流（含 AI 聚合接口）
│   ├── spzx-modules/spzx-product   商品/SKU/库存（含 AI 聚合接口）
│   ├── sql/ai_demo_orders.sql      联调演示订单（幂等）
│   └── README.md
├── customer-service-backend/     客服服务（Python）
│   ├── app/infrastructure/commerce_spzx.py   ← spzx 适配器（唯一取数出口）
│   ├── flow_config/user_flows.yml            槽位与话术流程
│   └── README.md
├── knowledge-service/            知识库服务（Python）
│   ├── knowledge/                  导入/查询两个 FastAPI 应用
│   ├── docker-compose.yml          Milvus/MinIO/Mongo/etcd/Attu 编排
│   └── README.md
├── _kb_docs/                     已入库的电商政策文档（退款/物流）
├── docker-compose.yml            中间件编排（与 knowledge-service 内那份一致）
├── verify_e2e.py                 联调自检
├── start_all.bat                 一键启动（Windows）
└── stop_all.bat                  一键停止
```

---

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| 客服查订单回"暂时查不到" | 先直连 spzx 接口确认；常见是 9207 没起、订单号不存在、或少带 `from-source: inner` |
| `{"code":500,"msg":"没有内部访问权限"}` | 内部接口必须带请求头 `from-source: inner` |
| spzx 服务端口不是 9205/9207 | 环境变量 `SERVER_PORT` 覆盖了配置，启动参数显式 `--server.port=xxx` |
| Java 启动报 `Port 49247 in use` | 同上，Spring Boot 读到了外部注入的 `SERVER_PORT` |
| RAG 回"暂时查不到" | 8001 没起，或 `RAG_SERVICE_TIMEOUT` < 实际耗时（默认 120s） |
| 知识库服务启动 `Segmentation fault` | 8000 与 8001 同时加载 BGE-M3，需串行启动 |
| 本地请求 502 | 系统代理劫持回环，curl 加 `--noproxy '*'`，Python 用 `session.trust_env=False` |
| `mvn` 报 `invalid target release: 21` | 命令行 `JAVA_HOME` 指向 JDK8，切到 JDK21 再构建 |

---

## 上传 GitHub 说明

三个项目是**互相独立**的仓库关系（没有父子模块依赖），建议分别建仓库推送：

```
仓库 1：spzx-parent                （Java 后端，.gitignore 已排除 target/、node_modules/、.idea/）
仓库 2：customer-service-backend   （Python 服务，已排除 .venv/、__pycache__/、.env）
仓库 3：knowledge-service          （Python 服务，已排除 .venv/、temp-files/、knowledge/.env）
```

推之前请确认：

1. **`customer-service-backend/.env` 和 `knowledge-service/knowledge/.env` 里有真实 API key**，
   两个文件都已被 `.gitignore` 排除，仓库里只带 `.env.example`。
   如果之前提交过，用 `git rm --cached` 摘掉并轮换 key。
2. `spzx-parent` 的数据库密码、支付宝密钥都在 **Nacos** 里，不要拷回 `application.yml`。
3. `verify_e2e.py`、`start_all.bat`、`stop_all.bat`、`sql/`、`_kb_docs/` 可放进任一仓库，
   或在三者之上再建一个总仓库（把三个目录作为子目录，各自保留 .gitignore）。
