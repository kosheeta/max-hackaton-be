import hashlib
import hmac
import json
import urllib.parse

from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import ParseMode
from maxapi.types import Attachment
from pydantic import BaseModel
from rewire import config, simple_plugin, DependenciesModule, logger

from src.models import InitData

plugin = simple_plugin()


@config
class Config(BaseModel):
    token: str


@plugin.setup()
async def create_bot() -> Bot:
    return Bot(Config.token, parse_mode=ParseMode.HTML)


@plugin.setup()
async def create_dispatcher() -> Dispatcher:
    return Dispatcher()


@plugin.run()
async def start_bot(bot: Bot, dispatcher: Dispatcher):
    await dispatcher.start_polling(bot)


async def get_app_link() -> str:
    bot_user = await get_bot().get_me()
    return f'https://max.ru/{bot_user.username}?startapp'


async def send_user_message(user_id: int, text: str, *attachments: Attachment):
    try:
        await get_bot().send_message(
            user_id=user_id,
            text=text,
            attachments=[*attachments]
        )
    except Exception as e:
        logger.error(f'Failed to send message to (user_id={user_id}): {e}')


def parse_init_data(init_data_string: str) -> InitData:
    parsed_data = {
        key: value[0]
        for key, value in urllib.parse.parse_qs(init_data_string, strict_parsing=True).items()
    }

    if 'user' in parsed_data:
        parsed_data['user'] = json.loads(urllib.parse.unquote(parsed_data['user']))
    if 'chat' in parsed_data:
        parsed_data['chat'] = json.loads(urllib.parse.unquote(parsed_data['chat']))

    init_data = InitData(**parsed_data)
    secret_key = hmac.new(
        key=b'WebAppData',
        msg=Config.token.encode(),
        digestmod=hashlib.sha256
    ).digest()

    data_check_pairs = []
    for key, value in sorted(parsed_data.items()):
        if key == 'hash':
            continue

        if isinstance(value, dict):
            value = json.dumps(value, separators=(',', ':'), ensure_ascii=False)

        data_check_pairs.append(f'{key}={value}')

    data_check_string = '\n'.join(data_check_pairs)
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    if calculated_hash != init_data.hash:
        raise ValueError('Invalid init data!')

    return init_data


def get_bot() -> Bot:
    return DependenciesModule.get().resolve(Bot)
