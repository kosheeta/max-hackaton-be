import asyncio
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.security import APIKeyHeader
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.intent import Intent
from maxapi.types import CallbackButton
from maxapi.types.attachments import Image
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from rewire import simple_plugin
from rewire_fastapi import Dependable
from rewire_sqlmodel import transaction

from src import redis, bot
from src.bot import Config
from src.main_flow import OpenChallengePayload, RatingPayload
from src.models import User, ChallengeResponse, ChallengeElementResponse, CompleteChallengeRequest, CompleteChallengeResponse, Challenge
from src.utils import parse_init_data_unsafe, validate_init_data

plugin = simple_plugin()
router = APIRouter()

MAX_ERROR = 1000


@Dependable
@transaction(0)
async def user_dependency(init_data_str: Annotated[str, Depends(APIKeyHeader(name='X-Init-Data'))]) -> Optional[User]:
    try:
        init_data = parse_init_data_unsafe(init_data_str)
        validate_init_data(init_data, Config.token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail='Invalid init data!') from e

    if not init_data.user:
        raise HTTPException(status_code=401, detail='No user in the init data!')

    user = await User.get(init_data.user.id)
    if not user:
        raise HTTPException(status_code=401, detail='No user found for this init data!')

    return user


@router.get('/api/challenges', response_model=ChallengeResponse)
@transaction(0)
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
@transaction(0)
async def complete_challenge(request: CompleteChallengeRequest, user: user_dependency.Result, background_tasks: BackgroundTasks):
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

    background_tasks.add_task(
        send_complete_challenge_message,
        user, final_score
    )

    return CompleteChallengeResponse(ok=True)


@transaction(0)
async def send_complete_challenge_message(user: User, score: float):
    if score >= 90:
        result_text = f'Невероятно! Твой город достиг {score}% доступности 🎉\nТы делаешь его по-настоящему дружелюбным!'
    elif score >= 70:
        result_text = f'Отлично! Город становится доступнее — уже {score}% 💪'
    elif score >= 50:
        result_text = f'Хорошо! Твой город достиг {score}% доступности, но есть куда расти 🔧'
    else:
        result_text = f'Первые шаги сделаны — {score}% доступности 🌱\nПопробуй завтра добиться большего!'

    await bot.send_user_message(user.id, result_text)
    await asyncio.sleep(3)

    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.row(CallbackButton(text='Перейти к рейтингу', payload=RatingPayload().pack(), intent=Intent.POSITIVE))
    inline_keyboard.row(CallbackButton(text='Вернуться к уровню', payload=OpenChallengePayload().pack(), intent=Intent.POSITIVE))

    completed_ids = await redis.get_user_completed_challenges(user.id)
    if await Challenge.get_next(completed_ids):
        await bot.send_user_message(
            user.id,
            'Возвращайся завтра — тебя ждёт новая локация и новые вызовы!\n'
            'Каждый день приближает тебя к городу без барьеров.',
            inline_keyboard.as_markup()
        )
    else:
        payload = await bot.upload_image('assets/certificate.png')
        await bot.send_user_message(
            user.id,
            'Ты — настоящий гений доступности!\n'
            'Твой город теперь открыт для всех — и это твоя заслуга.\n'
            'Вот твой сертификат создателя доступного города ☝️',
            Image(
                payload=payload,
                type=AttachmentType.IMAGE
            )
        )

    if user.last_challenge_message_id:
        await bot.delete_user_message(user.last_challenge_message_id)
        user.last_challenge_message_id = None
        user.add()


@plugin.setup()
def include_router(app: FastAPI):
    app.include_router(router)
