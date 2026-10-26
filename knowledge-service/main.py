"""知识库服务本地启动入口。

用法：
    python main.py            # 启动查询服务 8001（联调时用这个）
    python main.py import     # 启动导入服务 8000（往知识库灌文档时才用）

注意：两个服务都会加载 BGE-M3（约 2GB 显存），不要同时开，
      否则会 Segmentation fault —— 正确姿势是停 8001 → 导入 → 重开 8001。
"""
import sys

import uvicorn

QUERY_APP = "knowledge.api.query_router:create_app"
IMPORT_APP = "knowledge.api.import_router:create_app"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "query"
    if mode == "import":
        print("[knowledge-service] 启动导入服务 http://127.0.0.1:8000")
        uvicorn.run(IMPORT_APP, factory=True, host="127.0.0.1", port=8000)
    else:
        print("[knowledge-service] 启动查询服务 http://127.0.0.1:8001")
        uvicorn.run(QUERY_APP, factory=True, host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
