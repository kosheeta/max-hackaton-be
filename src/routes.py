import asyncio
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader
from maxapi.enums.intent import Intent
from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from rewire import simple_plugin
from rewire_fastapi import Dependable
from rewire_sqlmodel import transaction

from src import redis, bot
from src.bot import parse_init_data
from src.main_flow import OpenChallengePayload
from src.models import User, ChallengeResponse, ChallengeElementResponse, CompleteChallengeRequest, CompleteChallengeResponse

plugin = simple_plugin()
router = APIRouter()

MAX_ERROR = 1000


@Dependable
@transaction(1)
async def user_dependency(init_data_str: Annotated[str, Depends(APIKeyHeader(name='X-Init-Data'))]) -> Optional[User]:
    init_data = parse_init_data(init_data_str)
    if not init_data.user:
        raise HTTPException(status_code=401, detail='No user in the init data!')

    user = await User.get(init_data.user.id)
    if not user:
        raise HTTPException(status_code=401, detail='No user found for this init data!')

    return user


@router.get('/api/challenges', response_model=ChallengeResponse)
@transaction(1)
async def get_challenge(user: user_dependency.Result) -> ChallengeResponse:
    if not user.current_challenge:
        raise HTTPException(status_code=400, detail='No current challenge available!')

    return ChallengeResponse(
        **user.current_challenge.model_dump(),
        elements=[
            ChallengeElementResponse(**element.model_dump())
            for element in user.current_challenge.elements
        ]
    )


@router.post('/api/challenges/complete', response_model=CompleteChallengeResponse)
@transaction(1)
async def complete_challenge(request: CompleteChallengeRequest, user: user_dependency.Result):
    if not user.current_challenge:
        raise HTTPException(status_code=400, detail='No current challenge available!')

    last_score = await redis.get_user_challenge_score(user.id, user.current_challenge_id)
    if not last_score:
        user.last_completed_at = datetime.now()

    placed_elements = {element.id: element for element in request.placed_elements}
    total_error = sum(
        abs(placed_elements[element.id].x - element.target_x) + abs(placed_elements[element.id].y - element.target_y)
        for element in user.current_challenge.elements
        if element.id in placed_elements
    )

    final_score = round(max(0.0, 1 - min(total_error / MAX_ERROR, 1.0)) * 100, 1)
    await redis.set_user_challenge_score(user.id, user.current_challenge_id, final_score)

    average_score = await redis.get_user_average_score(user.id)
    await redis.set_user_score(user.id, average_score)

    user.average_score = average_score
    user.add()

    if final_score >= 90:
        result_text = f'Невероятно! Твой город достиг {final_score}% доступности 🎉\nТы делаешь его по-настоящему дружелюбным!'
    elif final_score >= 70:
        result_text = f'Отлично! Город становится доступнее — уже {final_score}% 💪'
    elif final_score >= 50:
        result_text = f'Хорошо! Твой город достиг {final_score}% доступности, но есть куда расти 🔧'
    else:
        result_text = f'Первые шаги сделаны — {final_score}% доступности 🌱\nПопробуй завтра добиться большего!'

    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.add(CallbackButton(
        text='Вернуться к уровню',
        payload=OpenChallengePayload().pack(),
        intent=Intent.POSITIVE
    ))

    await bot.send_user_message(user.id, result_text)
    await asyncio.sleep(1)

    await bot.send_user_message(
        user.id,
        'Возвращайся завтра — тебя ждёт новая локация и новые вызовы!\n'
        'Каждый день приближает тебя к городу без барьеров.',
        inline_keyboard.as_markup()
    )

    return CompleteChallengeResponse(ok=True)


@plugin.setup()
def include_router(app: FastAPI):
    app.include_router(router)
