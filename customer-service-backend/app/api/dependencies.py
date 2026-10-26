from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.dialogue_engine import DialogueEngine
from app.infrastructure import database
from app.repository.dialogue_state_repository import DialogueStateRepository
from app.service.dialogue_service import DialogueService

_dialogue_engine: DialogueEngine | None = None


def init_engine(engine: DialogueEngine) -> None:
    global _dialogue_engine
    _dialogue_engine = engine


def get_engine() -> DialogueEngine:
    if _dialogue_engine is None:
        raise ValueError("DialogueEngine has not been initialized.")
    return _dialogue_engine


async def get_db():
    if database.session_factory is None:
        raise ValueError("Database engine has not been initialized.")
    async with database.session_factory() as session:
        yield session


async def get_dialogue_service(
        engine: DialogueEngine = Depends(get_engine),
        db: AsyncSession = Depends(get_db),
) -> DialogueService:
    repo = DialogueStateRepository(db)
    return DialogueService(dialogue_state_repository=repo, dialogue_engine=engine)


async def get_dialogue_state_repository(
        db: AsyncSession = Depends(get_db),
) -> DialogueStateRepository:
    return DialogueStateRepository(db)
