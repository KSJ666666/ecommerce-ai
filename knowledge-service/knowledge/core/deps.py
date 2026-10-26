from functools import cache, lru_cache

from knowledge.service.query_service import QueryService
from knowledge.service.upload_service import UploadService


@cache  # 缓存注解（把实例缓存一份，实现单例效果）
# @lru_cache  # 带淘汰机制，缓存达到阈值时按 LRU 淘汰
def get_upload_file_service():
    return UploadService()


def get_query_service():
    """查询服务：query_router 的 /query、/stream、/history 都依赖它。"""
    return QueryService()
