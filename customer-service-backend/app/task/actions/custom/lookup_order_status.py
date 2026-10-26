from app.task.actions.base import Action, ActionResult
from app.task.actions.custom.shared import _build_order_summary, fetch_order
from app.domain.state import DialogueState


class LookupOrderStatusAction(Action):
    """Fetches order status and summary from the e-commerce service."""

    name = "action_lookup_order_status"

    async def run(self, state: DialogueState, **kwargs: object) -> ActionResult:
        order_number = str(state.get_slot("order_number") or "").strip()
        payload = await fetch_order(order_number)

        if payload is None:
            return ActionResult(slot_updates={
                "order_status": "查询失败",
                "order_summary": "暂时无法查到该订单信息，请稍后再试。",
            })

        return ActionResult(slot_updates={
            # 接口返回的 status_desc 自带句号，而流程模板后面还会拼一个"。"，
            # 不去掉的话会渲染成"发出。。订单金额"，这里统一剥掉尾部句号。
            "order_status": str(payload.get("status_desc") or payload.get("status") or "未知").rstrip("。 "),
            # 摘要本身以句号收尾（模板在它后面不再补标点），所以这里只去空格
            "order_summary": _build_order_summary(payload).strip(),
        })
