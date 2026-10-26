# spzx —— 电商业务后端（Spring Cloud 微服务）

电商 AI 三方联调中的**业务基座**：商品、订单、购物车、支付、用户等能力都在这里。
AI 客服（`../customer-service-backend`）通过 HTTP 内部接口读取订单/物流/商品数据，不直连数据库。

```
浏览器 / H5  ──> spzx-gateway(8080) ──> spzx-product(9205) / spzx-order(9207) / ...
                                              ▲
                                              │ 内部接口 + from-source: inner
                                      客服服务(18082)
```

> 本项目基于 RuoYi-Cloud 微服务脚手架改造，业务侧为通用电商场景实现
> （商品/订单/购物车/支付/用户），并在订单/商品模块补了一层**面向 AI 客服的聚合接口**（见第五节）。

---

## 一、技术栈

| 组件 | 版本 | 说明 |
|---|---|---|
| JDK | 21 | 编译目标 21，代码使用 `switch` 表达式等新语法 |
| Spring Boot | 3.0.5 | |
| Spring Cloud | 2022.0.2 | |
| Spring Cloud Alibaba | 2022.0.0.0-RC2 | Nacos 注册/配置中心 |
| MyBatis-Plus | 3.5.3.1 | |
| MySQL | 8.0 | 分库：每个微服务一个库 |
| Redis | 6/7 | 购物车、防重令牌、商品缓存、验证码 |
| RabbitMQ | 3.x | 延迟消息取消超时未支付订单（需 `x-delayed-message` 插件） |
| Nacos | 2.x | 配置中心 + 注册中心 |
| Vue3 + Vite + Element Plus | — | `spzx-ui` 管理端 / H5 |

---

## 二、模块结构

```
spzx-parent
├── spzx-gateway            网关，统一入口                      8080
├── spzx-auth               登录认证，发 JWT                     9200
├── spzx-api                微服务之间共享的接口与实体（Feign 契约）
│   ├── spzx-api-product        ProductSku / SkuStockVo / RemoteProductService
│   ├── spzx-api-order          OrderInfo / OrderItem / RemoteOrderInfoService
│   ├── spzx-api-cart           CartInfo / RemoteCartService
│   ├── spzx-api-user           UserInfo / UserAddress / RemoteUserInfoService
│   └── spzx-api-system         SysUser / SysDictData / RemoteUserService
├── spzx-common             公共能力
│   ├── spzx-common-core        统一响应 R/AjaxResult、BaseEntity、异常
│   ├── spzx-common-security    @InnerAuth 内部调用鉴权、@RequiresLogin
│   ├── spzx-common-redis       RedisTemplate 封装、缓存切面
│   ├── spzx-common-rabbit      RabbitService（普通/延迟消息）
│   ├── spzx-common-log         操作日志切面
│   ├── spzx-common-datasource  多数据源
│   ├── spzx-common-datascope   数据权限
│   └── spzx-common-seata       分布式事务（本项目未启用）
├── spzx-modules            业务微服务
│   ├── spzx-product            商品/SKU/库存                   9205
│   ├── spzx-user               会员/收货地址                    9206
│   ├── spzx-order              下单/订单/物流                   9207
│   ├── spzx-channel            渠道（占位）                     9208
│   ├── spzx-cart               购物车                           9209
│   ├── spzx-payment            支付宝沙箱支付                    9210
│   ├── spzx-system             系统管理（脚手架自带）             9201
│   ├── spzx-gen                代码生成（脚手架自带）             9202
│   ├── spzx-job                定时任务（脚手架自带）             9203
│   └── spzx-file               文件/MinIO 上传                  9300
├── spzx-visual/spzx-monitor  Spring Boot Admin 监控             9100
├── spzx-ui                  Vue3 管理端 + H5 商城                 80
├── docker                   中间件编排参考
└── sql                      AI 客服联调用的演示订单脚本
```

**三方联调真正需要启动的只有**：`spzx-product`、`spzx-order`（外加 Nacos/MySQL/Redis/RabbitMQ）。
`cart`/`payment`/`gateway`/`auth` 只在跑完整购物链路（下单→支付）时才需要。

---

## 三、环境要求

| 依赖 | 要求 | 检查方式 |
|---|---|---|
| JDK | 17+（推荐 21） | `java -version` |
| Maven | 3.6+ | `mvn -v` |
| MySQL | 8.0 | `mysql -uroot -p -e "select 1"` |
| Redis | 6/7，需密码（配置里是 `123456`） | `redis-cli -a 123456 ping` |
| RabbitMQ | 3.x + 延迟消息插件（延迟取消订单用） | 管理台 15672 |
| Nacos | 2.x 单机即可 | `http://127.0.0.1:8848/nacos` |
| Node | 18+（只有改前端时用） | `node -v` |

### 数据库

各微服务独立库，需先建库并导入各自表结构与数据：

| 库名 | 归属服务 |
|---|---|
| `spzx-product` | spzx-product |
| `spzx-order` | spzx-order |
| `spzx-user` | spzx-user |
| `spzx-system` | spzx-system / spzx-auth |
| `spzx-payment` | spzx-payment |

连接信息不写在代码里，统一在 **Nacos 的 `spzx-xxx-dev.yml`** 中（见下）。

### Nacos 配置

启动前 Nacos 中必须存在以下 dataId（group 均为 `DEFAULT_GROUP`）：

```
application-dev.yml        # 共享：Feign 超时、sentinel 开关、actuator
spzx-gateway-dev.yml
spzx-auth-dev.yml
spzx-product-dev.yml       # 数据源、Redis、RabbitMQ、MyBatis-Plus
spzx-order-dev.yml
spzx-user-dev.yml
spzx-payment-dev.yml       # 含支付宝沙箱参数
spzx-file-dev.yml          # MinIO
spzx-system-dev.yml / spzx-gen-dev.yml / spzx-job-dev.yml / spzx-channel-dev.yml / spzx-cart-dev.yml
sentinel-spzx-gateway      # 网关限流规则（JSON）
```

`spzx-product-dev.yml` 的关键片段（其余服务同构，只改库名）：

```yaml
spring:
  datasource:
    url: jdbc:mysql://127.0.0.1:3306/spzx-product?allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=Asia/Shanghai
    username: root
    password: 你的密码
  data:
    redis:
      host: 127.0.0.1
      port: 6379
      password: 123456
  rabbitmq:
    host: 127.0.0.1
    port: 5672
    username: guest
    password: guest
```

> 换机器部署时，改 Nacos 里的配置即可，不用改代码；`bootstrap.yml` 里只留 Nacos 地址和端口。

---

## 四、启动

### 方式一：IDEA（日常开发）

1. 打开 `spzx-parent`，确认 Project SDK 为 21、Maven 已加载完依赖。
2. 依次启动 `SpzxProductApplication`(9205)、`SpzxOrderApplication`(9207)。
3. 需要完整购物链路时再启动 `spzx-gateway`、`spzx-auth`、`spzx-user`、`spzx-cart`、`spzx-payment`。

### 方式二：命令行打包后运行

```bash
# 只打三方联调需要的两个模块（-am 会一并编译 spzx-api / spzx-common 等依赖模块）
mvn -DskipTests -pl spzx-modules/spzx-order,spzx-modules/spzx-product -am package

java -jar spzx-modules/spzx-product/target/spzx-product.jar --server.port=9205
java -jar spzx-modules/spzx-order/target/spzx-order.jar   --server.port=9207
```

> 显式带 `--server.port` 是有原因的：Spring Boot 会读环境变量 `SERVER_PORT`，
> 有些工具/容器会注入它，导致服务跑到随机端口上（本机踩过 `49247` 的坑）。

### 演示数据（重要）

真实下单产生的 `order_no` 是 32 位 UUID，让用户在对话框里手打不现实；而且历史订单大多已取消。
执行下面脚本会插入 4 条**可读订单号**的演示订单（待付款/待发货/已发货/已完成各一条），幂等可重复执行：

```bash
mysql -uroot -p --default-character-set=utf8mb4 < sql/ai_demo_orders.sql
```

得到：`SP202610260001`（待发货）、`SP202610260002`（已发货）、`SP202610260003`（已完成）、`SP202610260004`（待付款）。

---

## 五、面向 AI 客服的内部接口

AI 客服不直连数据库，也不需要理解 `OrderInfo` 实体里那堆用不上的字段，
本模块对外提供了三个「聚合视图」接口。它们和 Feign 内部调用走同一套鉴权：
**请求头必须带 `from-source: inner`**，否则返回 `{"code":500,"msg":"没有内部访问权限，不允许访问"}`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/orderInfo/inner/ai/{orderNo}` | 订单聚合视图：状态文案、金额、收货信息（手机号脱敏）、商品明细 |
| GET | `/orderInfo/inner/logistics/{orderNo}` | 物流状态：按订单状态机推导（未接入承运商，运单号为空） |
| GET | `/product/inner/ai/sku/{skuId}` | SKU 聚合视图：名称、售价、可用库存、规格键值对 |

示例：

```bash
curl "http://127.0.0.1:9207/orderInfo/inner/ai/SP202610260001" -H "from-source: inner"
# {"code":200,"data":{"orderNo":"SP202610260001","orderStatus":1,
#  "statusDesc":"商家正在备货，尚未发货","totalAmount":1999.00,
#  "receiverName":"孔少杰","receiverPhoneMasked":"137****2456",
#  "receiverAddress":"河南省新乡市牧野区建设东路46号","createTime":"2026-10-26 09:27",
#  "items":[{"productId":3,"title":"小米 红米Note10 5G手机 红色 + 8G","quantity":1,"price":1999.00}]}}

curl "http://127.0.0.1:9205/product/inner/ai/sku/3" -H "from-source: inner"
```

**为什么不让客服直接调实体接口？** 后台改一个字段名就会把 AI 链路打挂；
聚合视图是双方约定的稳定契约，字段增减只影响本模块的 `AiOrderView` / `AiSkuView`，
客服侧（`app/infrastructure/commerce_spzx.py`）只是几个字段改名，不动业务逻辑。

其他内部接口（供 Feign 使用）：`/orderInfo/inner/getOrderInfo/{orderNo}`、
`/orderInfo/inner/updateOrderStatus/{orderNo}/{orderStatus}`、
`/product/getProductSku/{skuId}`、`/product/checkStockAndSubStock/{skuId}/{skuNum}`、
`/product/unlockStock/{skuId}/{skuNum}`。

---

## 六、与 AI 服务联调

客服服务（`../customer-service-backend`）的 `.env` 指向本项目的两个服务：

```ini
SPZX_ORDER_BASE_URL=http://127.0.0.1:9207
SPZX_PRODUCT_BASE_URL=http://127.0.0.1:9205
```

启动顺序：Nacos/MySQL/Redis/RabbitMQ → `spzx-product` → `spzx-order` → 客服服务(18082) → 知识库服务(8001)。

验证：

```bash
cd ..            # 到联调包根目录
python verify_e2e.py           # 端口 + 健康接口
python verify_e2e.py --full    # 端到端对话
```

实测对话（客服 → 本服务）：

```
用户：帮我查订单状态
客服：请告诉我你的订单号。
用户：SP202610260001
客服：订单SP202610260001当前状态是：商家正在备货，尚未发货。订单金额 ¥1999.00。商品：小米 红米Note10 5G手机 红色 + 8G。
```

---

## 七、常见问题

| 现象 | 原因与处理 |
|---|---|
| 启动后端口不是 9205/9207 | 环境变量 `SERVER_PORT` 覆盖了配置，启动参数显式加 `--server.port=9207` |
| 调内部接口返回 `code:500 没有内部访问权限` | 少了请求头 `from-source: inner` |
| `No spring.config.import property has been defined` | 缺 `bootstrap.yml` 或没引 `spring-cloud-starter-bootstrap` |
| 启动卡在 `Located property source` 后报 Nacos 超时 | Nacos 没起，或 `bootstrap.yml` 里的地址/命名空间不对 |
| `Table 'spzx-product.product_sku' doesn't exist` | 库没建或没导数据，见第三节 |
| Feign 调用报 `Read timed out` | `application-dev.yml` 里 `feign.client.config.default.readTimeout` 默认 30s，慢接口需放宽 |
| 购物车/令牌相关接口 500 | Redis 密码不对，检查 Nacos 中 `spring.data.redis.password` |
| `mvn` 报 `invalid target release: 21` | 本机 `JAVA_HOME` 指向 JDK8，临时切到 21：`set JAVA_HOME=D:\develop\Java\jdk-21` |

---

## 八、许可

基于 MIT 许可的开源微服务脚手架改造，许可声明见 `LICENSE`。
