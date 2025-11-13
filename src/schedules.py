from apscheduler.schedulers.asyncio import AsyncIOScheduler
from maxapi.enums.intent import Intent
from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from rewire import simple_plugin
from rewire_sqlmodel import transaction, session_context

from src import redis, bot
from src.main_flow import OpenChallengePayload
from src.models import User, Challenge

plugin = simple_plugin()


@transaction(1)
async def send_challenge_notifications():
    inline_keyboard = InlineKeyboardBuilder()
    inline_keyboard.add(CallbackButton(text='Вперёд!', payload=OpenChallengePayload().pack(), intent=Intent.POSITIVE))

    for user in await User.get_all():
        if not user.current_challenge_id or not user.next_challenge_ready:
            continue

        completed_ids = await redis.get_user_completed_challenges(user.id)
        if user.current_challenge_id not in completed_ids:
            continue

        next_challenge = await Challenge.get_next(completed_ids)
        if not next_challenge:
            continue

        user.last_completed_at = None
        user.current_challenge = next_challenge
        user.add()

        await session_context.get().commit()
        await bot.send_user_message(
            user.id,
            'Доброе утро! Сегодня тебя ждёт новая локация.'
            'Готов продолжить строить город без барьеров?',
            inline_keyboard.as_markup()
        )


@plugin.run()
async def start_schedules():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_challenge_notifications, 'cron', hour=10, minute=0)
    scheduler.start()
