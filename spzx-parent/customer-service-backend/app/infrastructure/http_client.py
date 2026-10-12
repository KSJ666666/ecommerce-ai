import asyncio

import httpx
from httpx import AsyncClient

http_client: AsyncClient = None


# 定义一个初始化函数:
def init_http_client():
    global http_client
    http_client = httpx.AsyncClient()



# 定义一个关闭远程连接的函数：
async def close_http_client():
    if http_client:
        await http_client.aclose()


if __name__ == '__main__':
    async def test():
        init_http_client()
        result = await http_client.get("http://127.0.0.1:18081/users/u1001/orders")
        print(result.json()["data"]["orders"])
        await close_http_client()

    asyncio.run(test())