import json

from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.upload_type import UploadType
from maxapi.types import Attachment, OtherAttachmentPayload
from pydantic import BaseModel
from rewire import config, simple_plugin, DependenciesModule, logger

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


async def send_user_message(user_id: int, text: str, *attachments: Attachment):
    try:
        await get_bot().send_message(user_id=user_id, text=text, attachments=[*attachments])
    except Exception as e:
        logger.error(f'Failed to send message (user_id={user_id}): {e}')


async def delete_user_message(message_id: str):
    await get_bot().delete_message(message_id)


async def upload_image(file_path: str) -> OtherAttachmentPayload:
    upload_url = await get_bot().get_upload_url(UploadType.IMAGE)
    upload_result = await get_bot().upload_file(upload_url.url, file_path, UploadType.IMAGE)

    photos_data = json.loads(upload_result)['photos']
    photo_data = next(iter(photos_data.values()))

    return OtherAttachmentPayload(
        token=photo_data['token'],
        url=upload_url.url
    )


def get_bot() -> Bot:
    return DependenciesModule.get().resolve(Bot)
