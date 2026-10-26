from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config.config import settings
from app.infrastructure.http_client import http_client
from app.task.actions.custom import shared as commerce_shared

if TYPE_CHECKING:
    from app.knowledge.context_builder import KnowledgeContext


@dataclass(slots=True)
class KnowledgeChunk:
    """A piece of retrieved knowledge to be injected into the LLM prompt."""

    content: str


class KnowledgeProvider:
    """
    Base class for one knowledge source.

    Current source taxonomy:
      - API: structured real-time business facts
      - FAQ: curated standard Q&A
      - RAG: semantic retrieval over documentation
    """

    provider_id = ""

    async def retrieve(self, query: str, context: "KnowledgeContext") -> list[KnowledgeChunk]:
        return []


class KnowledgeProviderRegistry:
    """Lookup table for planner-selected providers."""

    def __init__(self, providers: list[KnowledgeProvider]) -> None:
        self._providers_by_id = {p.provider_id: p for p in providers if p.provider_id}

    def get(self, provider_id: str) -> KnowledgeProvider | None:
        return self._providers_by_id.get(provider_id)


class ProductApiProvider(KnowledgeProvider):
    """Fetch product facts from the e-commerce service."""

    provider_id = "api.product"

    async def _fetch(self, product_id: str) -> dict | None:
        return await commerce_shared.fetch_product(product_id)

    async def retrieve(self, query: str, context: "KnowledgeContext") -> list[KnowledgeChunk]:
        product_id = context.product_id
        if not product_id:
            return []

        payload = await self._fetch(product_id)
        if payload is None:
            return [KnowledgeChunk(
                content=(
                    f"商品ID：{product_id}\n"
                    "当前系统中没有查到完整商品资料，或商品服务暂时不可用。\n"
                    "如用户咨询具体参数、价格或售后，请明确告知暂时没有查到完整商品信息。"
                ),
            )]

        return [KnowledgeChunk(content=self._render(payload, product_id))]

    @staticmethod
    def _render(product: dict, product_id: str) -> str:
        attributes = product.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}
        specs = "；".join(f"{k}：{v}" for k, v in attributes.items()) or "当前资料中未提供更详细的规格参数"
        return (
            f"商品ID：{product.get('product_id', product_id)}\n"
            f"商品名称：{product.get('title', '未知商品')}\n"
            f"商品描述：{product.get('description', '当前资料中未提供商品描述')}\n"
            f"价格：{product.get('price', '未知')}\n"
            f"库存状态：{product.get('stock_status', '未知')}\n"
            f"规格参数：{specs}\n"
            "发货信息：请结合店铺库存和订单收货地址进一步确认。\n"
            "售后服务：如商品页未单独说明，默认以店铺售后政策和平台规则为准。"
        )


class OrderApiProvider(KnowledgeProvider):
    """Fetch order facts, including logistics, from the e-commerce service."""

    provider_id = "api.order"

    async def _fetch_order(self, order_number: str) -> dict | None:
        return await commerce_shared.fetch_order(order_number)

    async def _fetch_logistics(self, order_number: str) -> dict | None:
        return await commerce_shared.fetch_logistics(order_number)

    async def retrieve(self, query: str, context: "KnowledgeContext") -> list[KnowledgeChunk]:
        order_number = context.order_number
        if not order_number:
            return []

        order_payload, logistics_payload = await asyncio.gather(
            self._fetch_order(order_number),
            self._fetch_logistics(order_number),
        )

        if order_payload is None and logistics_payload is None:
            return [KnowledgeChunk(
                content=f"订单号：{order_number}\n当前系统中没有查到订单或物流信息，或订单服务暂时不可用。",
            )]

        return [KnowledgeChunk(content=self._render(order_number, order_payload, logistics_payload))]

    @staticmethod
    def _render(order_number: str, order_payload: dict | None, logistics_payload: dict | None) -> str:
        parts = [f"订单号：{order_number}"]

        if order_payload:
            parts.append(f"订单状态：{order_payload.get('status_desc') or order_payload.get('status') or '未知'}")
            if order_payload.get("amount") not in (None, ""):
                parts.append(f"订单金额：¥{order_payload.get('amount')}")
            if receiver := str(order_payload.get("receiver_name") or "").strip():
                parts.append(f"收货人：{receiver}")
            if phone := str(order_payload.get("receiver_phone_masked") or "").strip():
                parts.append(f"联系电话：{phone}")
            if address := str(order_payload.get("receiver_address") or "").strip():
                parts.append(f"收货地址：{address}")
            items = order_payload.get("items")
            if isinstance(items, list) and items:
                titles = [str(item.get("title") or "").strip() for item in items[:3] if isinstance(item, dict) and str(item.get("title") or "").strip()]
                if titles:
                    parts.append("订单商品：" + "、".join(titles))

        if logistics_payload:
            parts.append(f"物流公司：{logistics_payload.get('logistics_company') or '未知'}")
            parts.append(f"物流单号：{logistics_payload.get('tracking_number') or '未知'}")
            parts.append(f"物流状态：{logistics_payload.get('status_desc') or logistics_payload.get('status') or '未知'}")
            traces = logistics_payload.get("traces")
            if isinstance(traces, list) and traces:
                latest = traces[0] if isinstance(traces[0], dict) else {}
                trace_parts = [str(latest.get("time") or "").strip(), str(latest.get("desc") or "").strip()]
                if any(trace_parts):
                    parts.append("最新物流轨迹：" + " ".join(p for p in trace_parts if p))

        return "\n".join(parts)


class FaqKnowledgeProvider(KnowledgeProvider):
    """Placeholder FAQ provider. Interface is reserved for the next phase."""

    provider_id = "faq.default"


class RagKnowledgeProvider(KnowledgeProvider):
    """把用户问题转发给「知识库服务」这个独立部署的 RAG 服务，做语义检索增强。

    知识库服务内部会跑「向量检索 + HyDE + RRF 融合 + Rerank 重排 + 答案生成」，
    返回一段已组织好的答案文本，这里直接把它当作上下文喂给客服自己的 LLM。

    这是两个项目的衔接点：客服负责意图编排，知识库服务负责知识检索，
    两者通过 HTTP 解耦，谁挂了都不会把对方拖死。
    """

    provider_id = "rag.default"

    def _base_url(self) -> str:
        return settings.rag_service_url.rstrip("/")

    @staticmethod
    def _build_query(query: str, context: "KnowledgeContext") -> str:
        """把聚焦对象拼进问题。

        用户常问"这个商品怎么样""它怎么用"，这种指代直接丢给知识库是检索不到东西的，
        所以先把当前聚焦的商品/订单信息补进查询语句里。
        """
        parts: list[str] = []
        if context.product_id:
            parts.append(f"商品编号：{context.product_id}")
        if context.order_number:
            parts.append(f"订单号：{context.order_number}")
        parts.append(query)
        return " ".join(part for part in parts if part)

    async def retrieve(self, query: str, context: "KnowledgeContext") -> list[KnowledgeChunk]:
        question = (query or "").strip()
        if not question:
            return []

        try:
            r = await http_client.post(
                f"{self._base_url()}/query",
                json={"query": self._build_query(question, context), "is_stream": False},
                timeout=settings.rag_service_timeout,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:
            # 知识库不可用时不能把整个客服拖崩，但也不能让 LLM 凭空编造政策，
            # 所以显式塞一条"查不到"的上下文，由 responder 决定怎么措辞。
            return [KnowledgeChunk(
                content=(
                    "【知识库暂时不可用】本次没有检索到任何资料。"
                    "请明确告知用户暂时查不到相关信息，不要编造政策、参数或时效。"
                    f"（原因：{type(exc).__name__}）"
                ),
            )]

        answer = str(payload.get("answer") or "").strip()
        if not answer:
            return []

        return [KnowledgeChunk(content=answer)]
