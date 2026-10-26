from app.task.actions.base import Action, ActionResult
from app.task.actions.custom.shared import fetch_product
from app.domain.messages import BotMessage
from app.domain.state import DialogueState


class RecommendSimilarProductsAction(Action):
    """Placeholder for similar product recommendation (Phase 2)."""

    name = "action_recommend_similar_products"

    async def run(self, state: DialogueState, **kwargs: object) -> ActionResult:
        product_id = str(state.get_slot("product_id") or "").strip()
        label = product_id or "这件商品"

        payload = await fetch_product(product_id)
        if payload:
            label = str(payload.get("title") or "").strip() or label

        text = (
            f"我已经收到你对\"{label}\"的相似商品推荐需求。"
            "不过当前版本还没有接入正式的推荐系统，稍后可以继续补上这部分能力。"
        )
        return ActionResult(messages=[BotMessage(text=text)])
