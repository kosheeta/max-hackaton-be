import hashlib
import hmac
import json

import pytest

from src.models import InitData
from src.utils import validate_init_data


def generate_valid_init_data(bot_token: str) -> InitData:
    raw_data = {
        'auth_date': 100,
        'query_id': '123',
        'user': {
            'id': 1,
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'test',
            'language_code': 'en',
            'photo_url': 'http://example.com/avatar.jpg'
        },
        'chat': {
            'id': 2,
            'type': 'private'
        },
        'ip': '127.0.0.1',
    }

    secret_key = hmac.new(
        key=b'WebAppData',
        msg=bot_token.encode(),
        digestmod=hashlib.sha256
    ).digest()

    data_check_pairs = []
    for key, value in sorted(raw_data.items()):
        if isinstance(value, dict):
            value = json.dumps(value, separators=(',', ':'), ensure_ascii=False)

        data_check_pairs.append(f'{key}={value}')

    data_check_string = '\n'.join(data_check_pairs)
    data_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    raw_data['hash'] = data_hash

    print(InitData(**raw_data).model_dump())
    print(raw_data)


    return InitData(**raw_data)


def test_validate_init_data_success():
    bot_token = 'TEST_BOT_TOKEN'
    init_data = generate_valid_init_data(bot_token)






    validate_init_data(init_data, bot_token)


def test_validate_init_data_fail():
    bot_token = 'TEST_BOT_TOKEN'
    init_data = generate_valid_init_data(bot_token)
    init_data.hash = 'WRONGHASH'

    with pytest.raises(ValueError):
        validate_init_data(init_data, bot_token)
