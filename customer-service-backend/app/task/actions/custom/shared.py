from typing import Any

from app.infrastructure import commerce_spzx


async def fetch_order(order_id: str) -> dict | None:
    """按订单号查订单（spzx 的订单号是 UUID，不是主键 id）。"""
    return await commerce_spzx.fetch_order(order_id)


async def fetch_logistics(order_id: str) -> dict | None:
    """按订单号查物流。"""
    return await commerce_spzx.fetch_logistics(order_id)


async def fetch_product(product_id: str) -> dict | None:
    """按 skuId 查商品。"""
    return await commerce_spzx.fetch_product(product_id)


def _format_amount(amount: Any) -> str | None:
    """金额统一两位小数：jvm 返回的是 BigDecimal，序列化后 python 拿到的是 float，
    直接 f-string 会把 1999.00 打成 1999.0，播报出来很别扭。"""
    if amount is None or amount == "":
        return None
    try:
        return f"{float(amount):.2f}"
    except (TypeError, ValueError):
        return str(amount)


def _build_order_summary(payload: dict[str, Any]) -> str:
    parts = []
    amount = _format_amount(payload.get("amount"))
    if amount:
        parts.append(f"订单金额 ¥{amount}")
    items = payload.get("items") or []
    if items:
        titles = [str(item.get("title_snapshot") or "").strip() for item in items[:2] if item.get("title_snapshot")]
        if titles:
            parts.append("商品：" + "、".join(titles))
    # 结尾保留句号：流程模板是「…{{ order_status }}。{{ order_summary }}」，
    # 摘要自己带句号收尾，否则整段话会变成一个没有句末标点的长句。
    return "。".join(parts) + "。" if parts else ""
