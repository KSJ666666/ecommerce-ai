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
    # 商城API地址
    commerce_api_base_url: str
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



