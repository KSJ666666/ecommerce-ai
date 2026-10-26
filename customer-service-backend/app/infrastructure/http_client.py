import asyncio

import httpx

# 模块级直接创建客户端。
# 注意坑：如果写成 http_client = None + init_http_client() 动态赋值，
# 其他文件用 `from app.infrastructure.http_client import http_client` 时，
# 会在 import 那一刻就把 None 绑定进自己的命名空间，之后 init 再赋值也不会更新，
# 表现就是所有业务查询都静默失败（异常被 except 吞掉，前端只看到"查询失败"）。
http_client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)


async def close_http_client():
    """应用关闭时释放连接池。"""
    if http_client:
        await http_client.aclose()


if __name__ == '__main__':
    # 手工冒烟：验证到 spzx 订单服务的连通性（内部接口需要 from-source 头）
    async def test():
        result = await http_client.get(
            "http://127.0.0.1:9207/orderInfo/inner/ai/SP202610260001",
            headers={"from-source": "inner"},
        )
        print(result.json()["data"])
        await close_http_client()

    asyncio.run(test())
