from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dependencies import init_engine
from app.api.routers.chat_router import chat_router
from app.engine.dialogue_engine_builder import build_dialogue_engine
from app.infrastructure.database import init_db_engine, close_db_engine
from app.infrastructure.http_client import close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时装配引擎 + 建数据库连接池，关闭时释放资源。"""
    init_engine(build_dialogue_engine())
    init_db_engine()
    yield
    await close_db_engine()
    await close_http_client()


app = FastAPI(lifespan=lifespan)
app.include_router(chat_router)
