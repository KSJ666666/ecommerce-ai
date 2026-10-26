"""spzx（Java Spring Cloud 电商后端）的调用封装。

原来的电商后端是一个 Python FastAPI 服务（18081），只当"工具提供方"用。
现在这个角色由 spzx 微服务承担，调用方式换成 spzx 的内部接口契约：

    GET {spzx_order}/orderInfo/inner/ai/{orderNo}       订单聚合视图
    GET {spzx_order}/orderInfo/inner/logistics/{orderNo} 物流状态（按订单状态推导）
    GET {spzx_product}/product/inner/ai/sku/{skuId}     SKU 聚合视图

内部接口靠请求头 `from-source: inner` 放行（与 spzx 内部 Feign 调用同一套机制），
所以这套地址只应该出现在本机/内网，不要暴露到公网。

之所以让 Java 侧返回"聚合视图"而不是让这里解析 OrderInfo 实体：
实体里有行政区划编码、优惠券、审计字段一大堆客服根本用不上的东西，
一旦后台改字段名，AI 链路就跟着崩。视图是双方约定的稳定契约，改动只影响 Java 一侧。
"""

from urllib.parse import quote

from app.config.config import settings
from app.infrastructure.http_client import http_client

# 与 spzx-common-core 的 SecurityConstants.FROM_SOURCE 保持一致
INNER_HEADERS = {"from-source": "inner"}


async def _get_json(url: str) -> dict | None:
    """请求 spzx 内部接口并取出 R.data；网络异常、非 200 业务码、data 为空都返回 None。"""
    try:
        response = await http_client.get(url, headers=INNER_HEADERS)
        body = response.json()
    except Exception:
        # 客服链路的兜底原则：业务查询失败不能让整轮对话报错，交给上层给"暂时查不到"话术
        return None

    if not isinstance(body, dict) or body.get("code") not in (200, "200"):
        return None
    data = body.get("data")
    return data if isinstance(data, dict) else None


async def fetch_order(order_no: str) -> dict | None:
    """订单聚合视图 -> 客服侧统一的订单 dict。"""
    data = await _get_json(
        f"{settings.spzx_order_base_url.rstrip('/')}/orderInfo/inner/ai/{quote(order_no)}"
    )
    if not data:
        return None

    items = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        items.append(
            {
                "product_id": item.get("productId"),
                "title": title,
                # 下游话术用的是 title_snapshot（原 Python 后端的字段名），这里保持兼容
                "title_snapshot": title,
                "quantity": item.get("quantity"),
                "price": item.get("price"),
            }
        )

    return {
        "order_number": data.get("orderNo"),
        "status": data.get("orderStatus"),
        "status_desc": data.get("statusDesc"),
        "amount": data.get("totalAmount"),
        "created_at": data.get("createTime"),
        "receiver_name": data.get("receiverName"),
        "receiver_phone_masked": data.get("receiverPhoneMasked"),
        "receiver_address": data.get("receiverAddress"),
        "items": items,
    }


async def fetch_logistics(order_no: str) -> dict | None:
    """物流状态。spzx 未接入承运商，返回的 status_desc 是按订单状态机推导的文案。"""
    return await _get_json(
        f"{settings.spzx_order_base_url.rstrip('/')}/orderInfo/inner/logistics/{quote(order_no)}"
    )


async def fetch_product(sku_id: str) -> dict | None:
    """SKU 聚合视图 -> 客服侧统一的商品 dict。"""
    # spzx 的 skuId 是自增 bigint，传 "SKU10001" 这类旧格式只会拿到 400，直接短路更干净
    sku_id = str(sku_id or "").strip()
    if not sku_id.isdigit():
        return None

    data = await _get_json(
        f"{settings.spzx_product_base_url.rstrip('/')}/product/inner/ai/sku/{quote(sku_id)}"
    )
    if not data:
        return None

    attributes = data.get("attributes")
    return {
        "product_id": data.get("productId"),
        "title": str(data.get("title") or "").strip() or None,
        "description": data.get("productName"),
        "price": data.get("price"),
        "stock_status": data.get("stockStatus"),
        "attributes": attributes if isinstance(attributes, dict) else {},
        "cover_url": data.get("imageUrl"),
    }
