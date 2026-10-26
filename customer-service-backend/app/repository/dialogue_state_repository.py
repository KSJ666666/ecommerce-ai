from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dialogue_state import DialogueStateRecord
from app.domain.state import DialogueState


class DialogueStateRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, sender_id: str) -> DialogueState:
        result = await self._session.execute(
            select(DialogueStateRecord).where(DialogueStateRecord.sender_id == sender_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return DialogueState(sender_id=sender_id)
        return DialogueState.from_dict(json.loads(record.state_json))

    async def save(self, state: DialogueState) -> None:
        result = await self._session.execute(
            select(DialogueStateRecord).where(DialogueStateRecord.sender_id == state.sender_id)
        )
        record = result.scalar_one_or_none()
        state_json = json.dumps(state.to_dict(), ensure_ascii=False)
        if record is None:
            self._session.add(DialogueStateRecord(sender_id=state.sender_id, state_json=state_json))
        else:
            record.state_json = state_json
        await self._session.commit()
