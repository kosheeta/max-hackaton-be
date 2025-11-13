from maxapi import Router, Dispatcher
from maxapi.enums.intent import Intent
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import CommandStart
from maxapi.types import MessageCreated, CallbackButton, MessageCallback, LinkButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from rewire import simple_plugin
from rewire_sqlmodel import transaction

from src import redis
from src.bot import get_app_link
from src.models import User, Challenge

plugin = simple_plugin()
router = Router()


class ContinuePayload(CallbackPayload, prefix='continue'):
    pass


class OpenChallengePayload(CallbackPayload, prefix='open_challenge'):
    pass


@router.message_created(CommandStart())
async def start_command(event: MessageCreated):
    await User.get_or_create(
        event.from_user.user_id,
        name=event.from_user.first_name,
        username=event.from_user.username,
        avatar_url=event.from_user.avatar_url
    )

    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.add(CallbackButton(
        text='Да!',
        payload=ContinuePayload().pack(),
        intent=Intent.POSITIVE
    ))

    await event.message.answer(
        'Привет! Это игра <b>«Инклюзивный конструктор»</b> — здесь ты узнаешь, как сделать город удобным и доступным для всех. 🦮\n\n'
        'В каждом уровне ты будешь улучшать реальные места — и шаг за шагом учиться создавать инклюзивную среду.\n'
        'Пройди все задания и получи сертификат создателя доступного города!\n\n'
        'Готов начать?',
        attachments=[inline_keyboard.as_markup()]
    )


@router.message_callback(ContinuePayload.filter())
@transaction(1)
async def continue_callback(event: MessageCallback):
    user_scores = await redis.get_scores_leaderboard(limit=5)
    user_place = await redis.get_user_place(event.from_user.user_id)

    top_users = []
    for user_id, score in user_scores.items():
        user = await User.get(user_id)
        top_users.append((user, score))

    rating_lines = []
    for index, (user, score) in enumerate(top_users, start=1):
        rating_lines.append(f'<b>{index}) {user.name}: {score}%</b>')

    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.add(CallbackButton(
        text='Вперёд!',
        payload=OpenChallengePayload().pack(),
        intent=Intent.POSITIVE
    ))

    rating_text = '\n'.join(rating_lines)
    place_text = f'Твоё место: {user_place + 1} 🎖️' if user_place is not None else ''

    await event.message.answer(
        'Рейтинг точности среди создателей доступных городов:\n\n'
        f'<blockquote>{rating_text}</blockquote>\n\n'
        f'{place_text}'
    )

    if user_place == 0:
        await event.message.answer(
            'Ты на вершине рейтинга! 🏆\n'
            'Продолжай в том же духе, чтобы удержать лидерство!',
            attachments=[inline_keyboard.as_markup()]
        )
    else:
        await event.message.answer(
            'Всё ещё можно догнать лидеров!\n'
            'Хочешь перейти к первому заданию и подняться в рейтинге?',
            attachments=[inline_keyboard.as_markup()]
        )

    await event.message.delete()


@router.message_callback(OpenChallengePayload.filter())
@transaction(1)
async def next_challenge_callback(event: MessageCallback):
    user = await User.get(event.from_user.user_id)
    if not user.current_challenge:
        user.current_challenge = await Challenge.get_next()
        user.add()

    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.add(LinkButton(text='Открыть', link=await get_app_link()))

    await event.message.answer(
        user.current_challenge.description,
        attachments=[inline_keyboard.as_markup()]
    )

    await event.message.delete()


@plugin.setup()
def include_router(dispatcher: Dispatcher):
    dispatcher.include_routers(router)
