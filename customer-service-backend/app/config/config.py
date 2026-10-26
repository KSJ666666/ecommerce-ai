from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 读取.env 配置文件中的数据;
ENV_FILE = Path(__file__).parents[2] / ".env"

# 读取.env
class Settings(BaseSettings):
    # LLM 配置信息
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    # 电商后端：spzx（Java Spring Cloud 微服务）的内部接口地址
    # 订单/物流走 spzx-order(9207)，商品走 spzx-product(9205)
    spzx_order_base_url: str = "http://127.0.0.1:9207"
    spzx_product_base_url: str = "http://127.0.0.1:9205"
    # 知识库服务地址（RAG 问答接口；给默认值，.env 没配也能起）
    rag_service_url: str = "http://127.0.0.1:8001"
    # RAG 检索超时（秒）：要等知识库服务走完检索+重排+生成，比普通业务接口慢得多。
    # 实测：中间件未就绪时（连接重试拖慢）单次可达 63s，故默认给 120s。
    rag_service_timeout: float = 120.0
    # 数据库配置信息
    database_url: str
    # 服务器
    app_host: str
    app_port: int
    # 从配置文件中读取数据
    model_config = SettingsConfigDict(env_file=ENV_FILE)

settings = Settings()


# 测试
if __name__ == '__main__':
    print(settings.llm_model)



