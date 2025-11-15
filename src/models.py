from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
from rewire_sqlmodel import SQLModel, transaction
from sqlalchemy import BigInteger, Column
from sqlmodel import Field, Relationship


class User(SQLModel, table=True):
    id: int = Field(sa_type=BigInteger, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)

    name: str
    username: Optional[str]
    avatar_url: Optional[str]
    average_score: float = 0.0
    last_completed_at: Optional[datetime] = None
    last_challenge_message_id: Optional[str] = None
    received_certificate: bool = False

    current_challenge_id: Optional[str] = Field(default=None, foreign_key='challenge.id')
    current_challenge: Optional['Challenge'] = Relationship(
        sa_relationship_kwargs={'lazy': 'selectin'}
    )

    @property
    def next_challenge_ready(self) -> bool:
        return not self.last_completed_at or self.last_completed_at.date() < datetime.now().date()

    @classmethod
    async def get(cls, user_id: int) -> Optional['User']:
        return await cls.select().where(cls.id == user_id).first()

    @classmethod
    async def get_all(cls, **kwargs) -> List['User']:
        return list(await cls.select().filter_by(**kwargs).all())

    @classmethod
    @transaction(0)
    async def get_or_create(cls, user_id: int, **kwargs) -> 'User':
        return await cls.get(user_id) or cls(id=user_id, **kwargs).add()


class ChallengeElement(SQLModel, table=True):
    id: str = Field(primary_key=True)
    challenge_id: str = Field(foreign_key='challenge.id')
    name: str
    width: float
    target_x: float
    target_y: float


class Challenge(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    description: str
    scene_width: float
    scene_height: float

    elements: List[ChallengeElement] = Relationship(
        cascade_delete=True,
        sa_relationship_kwargs={'lazy': 'joined'}
    )

    @classmethod
    async def get_by_id(cls, challenge_id: str) -> Optional['Challenge']:
        return await cls.select().where(cls.id == challenge_id).first()

    @classmethod
    async def get_next(cls, completed_ids: Optional[List[str]] = None) -> Optional['Challenge']:
        if not completed_ids:
            return await cls.select().first()

        return await cls.select().where(cls.id.not_in(completed_ids)).first()


class Mailing(SQLModel, table=True):
    id: int = Field(sa_column=Column(primary_key=True, autoincrement=True))
    send_at: datetime
    message_text: str
    button_text: str
    button_url: str


class InitDataUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]
    photo_url: Optional[str]


class InitDataChat(BaseModel):
    id: int
    type: str


class InitData(BaseModel):
    auth_date: int
    query_id: str
    user: Optional[InitDataUser] = None
    chat: Optional[InitDataChat] = None
    hash: str
    ip: str


class ChallengeElementResponse(BaseModel):
    id: str
    name: str
    width: float


class ChallengeResponse(BaseModel):
    id: str
    name: str
    scene_width: float
    scene_height: float
    elements: List[ChallengeElementResponse]


class PlacedElementRequest(BaseModel):
    id: str
    x: float
    y: float


class CompleteChallengeRequest(BaseModel):
    placed_elements: List[PlacedElementRequest]


class CompleteChallengeResponse(BaseModel):
    ok: bool
