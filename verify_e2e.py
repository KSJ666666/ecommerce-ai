#!/usr/bin/env python
"""三方联调自检：spzx Java 电商后端 / 客服服务 / 知识库服务。

用法：
    python verify_e2e.py            # 快速检查：端口 + 健康接口（秒级）
    python verify_e2e.py --full     # 含端到端对话，每条 15~90s（RAG 链路较慢）
    python verify_e2e.py --full --order SP202610260001   # 指定演示订单号

依赖：pip install requests

设计说明：
  - 全部请求关闭代理（trust_env=False）。本机若设了 HTTP_PROXY，访问 127.0.0.1 会被劫持成 502。
  - spzx 的内部接口要求请求头 from-source: inner，这里统一带上。
  - 慢接口单独超时，不拖累快速检查。
"""
from __future__ import annotations

import argparse
import socket
import sys
import time

import requests

ORDER = "http://127.0.0.1:9207"
PRODUCT = "http://127.0.0.1:9205"
CUSTOMER = "http://127.0.0.1:18082"
KB_QUERY = "http://127.0.0.1:8001"

INNER = {"from-source": "inner"}

# 端口 -> (说明, 是否必需)
PORTS = {
    8848: ("Nacos 注册/配置中心", True),
    3306: ("MySQL", True),
    6379: ("Redis", True),
    5672: ("RabbitMQ", True),
    9207: ("spzx-order 订单服务", True),
    9205: ("spzx-product 商品服务", True),
    18082: ("客服服务 customer-service-backend", True),
    8001: ("知识库服务-查询", True),
    19530: ("Milvus", False),
    27017: ("MongoDB", False),
    9000: ("MinIO", False),
    8000: ("Attu 控制台 / 知识库服务-导入（两者抢同一端口）", False),
}

OK, BAD, WARN = "[OK]  ", "[FAIL]", "[WARN]"


def session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False          # 关键：绕过系统代理，否则本地请求会被拦成 502
    return s


S = session()


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def check_ports() -> bool:
    print("\n── 1. 端口存活 ──")
    all_ok = True
    for port, (name, required) in PORTS.items():
        up = port_open(port)
        tag = OK
        if not up:
            if required:
                tag = BAD
                all_ok = False
            else:
                tag = WARN          # 可选端口缺失只提示，不判失败
        print(f"  {tag} {port:<6} {name:<40} {'UP' if up else 'DOWN'}")
    return all_ok


def check_health(order_no: str) -> bool:
    print("\n── 2. 服务健康 ──")
    ok = True

    # 2.1 spzx-order 的 AI 聚合接口
    try:
        r = S.get(f"{ORDER}/orderInfo/inner/ai/{order_no}", headers=INNER, timeout=8)
        body = r.json()
        data = body.get("data") or {}
        good = r.status_code == 200 and body.get("code") == 200
        print(f"  {OK if good else BAD} spzx-order 订单视图 -> "
              f"{data.get('orderNo')} / {data.get('statusDesc')}")
        if not good:
            print(f"        原始响应: {str(body)[:200]}")
            print("        提示: 演示订单不存在时请先执行 spzx-parent/sql/ai_demo_orders.sql")
        ok &= good
    except Exception as exc:
        print(f"  {BAD} spzx-order 异常: {type(exc).__name__}: {exc}")
        ok = False

    # 2.2 spzx-product 的 AI 聚合接口
    try:
        r = S.get(f"{PRODUCT}/product/inner/ai/sku/3", headers=INNER, timeout=8)
        body = r.json()
        data = body.get("data") or {}
        good = r.status_code == 200 and body.get("code") == 200 and bool(data.get("title"))
        print(f"  {OK if good else BAD} spzx-product SKU 视图 -> "
              f"{data.get('title')} / {data.get('stockStatus')}")
        ok &= good
    except Exception as exc:
        print(f"  {BAD} spzx-product 异常: {type(exc).__name__}: {exc}")
        ok = False

    # 2.3 内部接口必须拦住不带 from-source 的裸请求（安全基线）
    try:
        r = S.get(f"{ORDER}/orderInfo/inner/ai/{order_no}", timeout=8)
        blocked = r.status_code == 200 and r.json().get("code") != 200
        print(f"  {OK if blocked else WARN} 内部接口鉴权 -> "
              f"{'已拦截未带 from-source 的请求' if blocked else '未拦截，请检查 InnerAuth'}")
    except Exception as exc:
        print(f"  {WARN} 内部接口鉴权检查跳过: {type(exc).__name__}: {exc}")

    # 2.4 客服服务
    try:
        r = S.get(f"{CUSTOMER}/openapi.json", timeout=5)
        good = r.status_code == 200 and "/api/chat" in r.text
        print(f"  {OK if good else BAD} 客服服务 /openapi.json -> {r.status_code}")
        ok &= good
    except Exception as exc:
        print(f"  {BAD} 客服服务 异常: {type(exc).__name__}: {exc}")
        ok = False

    # 2.5 知识库服务
    try:
        r = S.get(f"{KB_QUERY}/", timeout=8)
        good = r.status_code == 200 and r.json().get("flag") == "success"
        print(f"  {OK if good else BAD} 知识库服务 / -> {r.json()}")
        ok &= good
    except Exception as exc:
        print(f"  {BAD} 知识库服务 异常: {type(exc).__name__}: {exc}")
        ok = False

    return ok


def chat(sender: str, text: str, timeout: int = 200) -> str:
    r = S.post(f"{CUSTOMER}/api/chat",
               json={"sender_id": sender, "text": text},
               timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return " | ".join(m.get("text") or "" for m in data.get("messages", []))


def check_e2e(order_no: str) -> bool:
    print("\n── 3. 端到端对话 ──")
    ok = True

    # 3.1 客服 -> spzx-order：查订单（两轮填槽）
    print("  [3.1] 客服 -> spzx 订单服务（查订单，两轮）…")
    try:
        first = chat("verify_order", "帮我查订单状态")
        second = chat("verify_order", order_no)
        good = "订单号" in first and order_no in second and "查询失败" not in second
        print(f"        {OK if good else BAD} 第1轮: {first}")
        print(f"        {OK if good else BAD} 第2轮: {second}")
        ok &= good
    except Exception as exc:
        print(f"        {BAD} 异常: {type(exc).__name__}: {exc}")
        ok = False

    # 3.2 客服 -> spzx-order：查物流
    print("  [3.2] 客服 -> spzx 订单服务（查物流，两轮）…")
    try:
        first = chat("verify_logistics", "查一下物流")
        second = chat("verify_logistics", order_no)
        good = "物流" in second and order_no in second
        print(f"        {OK if good else BAD} 第1轮: {first}")
        print(f"        {OK if good else BAD} 第2轮: {second}")
        ok &= good
    except Exception as exc:
        print(f"        {BAD} 异常: {type(exc).__name__}: {exc}")
        ok = False

    # 3.3 客服 -> 知识库服务：知识问答（慢，走完整 RAG）
    print("  [3.3] 客服 -> 知识库服务（知识问答，约 20~60s）…")
    start = time.time()
    try:
        answer = chat("verify_rag", "退货政策是怎么规定的")
        cost = time.time() - start
        good = bool(answer.strip()) and "暂时" not in answer[:20]
        print(f"        {OK if good else BAD} 耗时 {cost:.1f}s -> {answer[:160]}")
        ok &= good
    except Exception as exc:
        print(f"        {BAD} 异常: {type(exc).__name__}: {exc}")
        ok = False

    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="包含端到端对话（慢）")
    parser.add_argument("--order", default="SP202610260001", help="演示订单号")
    args = parser.parse_args()

    print("=" * 66)
    print("电商 AI 三方联调自检  (spzx | 客服服务 | 知识库服务)")
    print("=" * 66)

    services_ok = check_ports()
    if not services_ok:
        print("\n必需端口未全部就绪，请先按启动顺序拉起服务再重试。")
        return 1

    health_ok = check_health(args.order)
    if not args.full:
        print("\n（未加 --full，跳过端到端对话）")
        print("\n结论：" + ("基础设施与健康检查通过" if health_ok else "健康检查有问题，见上"))
        return 0 if health_ok else 1

    e2e_ok = check_e2e(args.order)

    print("\n" + "=" * 66)
    if health_ok and e2e_ok:
        print("结论：全部通过，三方链路端到端可用。")
        return 0
    print("结论：存在失败项，见上面 [FAIL] 标记。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
