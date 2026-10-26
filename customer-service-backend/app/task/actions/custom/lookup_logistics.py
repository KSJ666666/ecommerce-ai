from app.task.actions.base import Action, ActionResult
from app.task.actions.custom.shared import fetch_logistics
from app.domain.state import DialogueState


class LookupLogisticsAction(Action):
    """Fetches logistics tracking information from the e-commerce service."""

    name = "action_lookup_logistics"

    async def run(self, state: DialogueState, **kwargs: object) -> ActionResult:
        order_number = str(state.get_slot("order_number") or "").strip()
        payload = await fetch_logistics(order_number)

        if payload is None:
            return ActionResult(slot_updates={
                "tracking_number": "未知",
                "logistics_company": "未知",
                "logistics_status": "暂时无法查到物流信息，请稍后再试。",
            })

        return ActionResult(slot_updates={
            "tracking_number": payload.get("tracking_number") or "未知",
            "logistics_company": payload.get("logistics_company") or "未知",
            # 同上：status_desc 自带句号，流程模板还会再加一个，剥掉避免"。。"
            "logistics_status": str(payload.get("status_desc") or payload.get("status") or "未知").rstrip("。 "),
        })
