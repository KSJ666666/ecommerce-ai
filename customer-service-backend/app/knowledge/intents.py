from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class KnowledgeIntent:
    id: str
    description: str
    provider_ids: list[str] = field(default_factory=list)
    requires_object: str | None = None


KNOWLEDGE_INTENTS: list[KnowledgeIntent] = [
    KnowledgeIntent(
        id="product_info",
        description="商品信息咨询",
        provider_ids=["faq.default", "rag.default"],
        requires_object="product",
    ),
    KnowledgeIntent(
        id="order_info",
        description="订单信息咨询",
        provider_ids=["faq.default", "rag.default"],
        requires_object="order",
    ),
    KnowledgeIntent(
        id="refund_policy",
        description="退款政策咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    KnowledgeIntent(
        id="return_policy",
        description="退货政策咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    KnowledgeIntent(
        id="shipping_policy",
        description="配送政策咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    KnowledgeIntent(
        id="platform_rule",
        description="平台规则咨询",
        provider_ids=["rag.default"],
    ),
    KnowledgeIntent(
        id="general_ecommerce_info",
        description="电商通用信息咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
]
