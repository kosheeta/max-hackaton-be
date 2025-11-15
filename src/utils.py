import hashlib
import hmac
import json
import urllib.parse

from src.models import InitData


def create_app_url(bot_username: str):
    return f'https://max.ru/{bot_username}?startapp'


def parse_init_data_unsafe(init_data_str: str) -> InitData:
    parsed_data = {
        key: value[0]
        for key, value in urllib.parse.parse_qs(init_data_str, strict_parsing=True).items()
    }

    if 'user' in parsed_data:
        parsed_data['user'] = json.loads(urllib.parse.unquote(parsed_data['user']))
    if 'chat' in parsed_data:
        parsed_data['chat'] = json.loads(urllib.parse.unquote(parsed_data['chat']))

    return InitData(**parsed_data)


def validate_init_data(init_data: InitData, bot_token: str):
    raw_data = init_data.model_dump()
    secret_key = hmac.new(
        key=b'WebAppData',
        msg=bot_token.encode(),
        digestmod=hashlib.sha256
    ).digest()

    data_check_pairs = []
    for key, value in sorted(raw_data.items()):
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
        raise ValueError(f'Invalid init data: {calculated_hash} | {init_data.hash}!')


def create_certificate_image(user_name: str, user_score: float) -> str:
    pass
