from maxapi import Router, Dispatcher
from maxapi.enums.intent import Intent
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import CommandStart
from maxapi.types import MessageCreated, CallbackButton, MessageCallback, LinkButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from rewire import simple_plugin
from rewire_sqlmodel import transaction

from src import redis
from src.models import User, Challenge
from src.utils import create_app_url

plugin = simple_plugin()
router = Router()


class RatingPayload(CallbackPayload, prefix='rating'):
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
    inline_keyboard.add(CallbackButton(text='Да!', payload=RatingPayload().pack(), intent=Intent.POSITIVE))

    await event.message.answer(
        'Привет! Это игра <b>«Инклюзивный конструктор»</b> — здесь ты узнаешь, как сделать город удобным и доступным для всех. 🦮\n\n'
        'В каждом уровне ты будешь улучшать реальные места — и шаг за шагом учиться создавать инклюзивную среду.\n'
        'Пройди все задания и получи сертификат создателя доступного города!\n\n'
        'Готов начать?',
        attachments=[inline_keyboard.as_markup()]
    )


@router.message_callback(RatingPayload.filter())
@transaction(1)
async def rating_callback(event: MessageCallback):
    user_scores = await redis.get_scores_leaderboard(limit=5)
    user_place = await redis.get_user_place(event.from_user.user_id)

    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.add(
        CallbackButton(
            text='Вперёд!',
            payload=OpenChallengePayload().pack(),
            intent=Intent.POSITIVE
        )
    )

    rating_text_parts = []
    if user_scores:
        top_users = []
        for user_id, score in user_scores.items():
            user = await User.get(user_id)
            top_users.append((user, score))

        rating_text = '\n'.join(
            f'{index}) {user.name}: {score}%'
            for index, (user, score) in enumerate(top_users, start=1)
        )

        rating_text_parts.append('Рейтинг точности среди создателей доступных городов:\n')
        rating_text_parts.append(f'<blockquote>{rating_text}</blockquote>\n')

        if user_place is not None:
            rating_text_parts.append(f'Твоё место: {user_place + 1} 🎖️\n')
            if user_place <= 1:
                rating_text_parts.append('Ты на вершине рейтинга! 🏆\nПродолжай в том же духе!')
            else:
                rating_text_parts.append(
                    'Всё ещё можно догнать лидеров!\n'
                    'Хочешь перейти к первому заданию и подняться в рейтинге?'
                )

    else:
        rating_text_parts.append(
            'Рейтинг пока пуст! 🌟\n'
            'Будь первым, кто откроет все задания и станет лидером!'
        )

    rating_text = '\n'.join(rating_text_parts)
    await event.message.answer(
        rating_text,
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
    inline_keyboard.add(LinkButton(text='Открыть', url=create_app_url(event.bot.me.username)))

    result = await event.message.answer(
        user.current_challenge.description,
        attachments=[inline_keyboard.as_markup()]
    )

    user.last_challenge_message_id = result.message.body.mid
    user.add()

    await event.message.delete()


@plugin.setup()
def include_router(dispatcher: Dispatcher):
    dispatcher.include_routers(router)
