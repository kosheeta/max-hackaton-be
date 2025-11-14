import json
import urllib.parse
from typing import Dict, Any

import pytest

from src.models import InitData
from src.utils import parse_init_data_unsafe


@pytest.mark.parametrize(
    'auth_date, query_id, user_data, chat_data, ip, hash_value',
    [
        (
                1588349205,
                '12345',
                {
                    'id': 1,
                    'username': 'testuser',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'language_code': 'en',
                    'photo_url': 'http://example.com/a.jpg',
                },
                {
                    'id': 10,
                    'type': 'private',
                },
                '127.0.0.1',
                'abcd1234'
        ),
        (
                1709895623,
                '999',
                {
                    'id': 2,
                    'username': 'another',
                    'first_name': 'Alice',
                    'last_name': 'Bob',
                    'language_code': 'ru',
                    'photo_url': 'http://example.com/x.png',
                },
                {
                    'id': 20,
                    'type': 'group',
                },
                '10.0.0.1',
                'ffffeeee'
        ),
    ]
)
def test_parse_init_data(auth_date: int, query_id: str, user_data: Dict[str, Any], chat_data: Dict[str, Any], ip: str, hash_value: str):
    init_string = (
        f'auth_date={auth_date}&'
        f'query_id={query_id}&'
        f'user={urllib.parse.quote(json.dumps(user_data))}&'
        f'chat={urllib.parse.quote(json.dumps(chat_data))}&'
        f'ip={ip}&'
        f'hash={hash_value}'
    )

    result = parse_init_data_unsafe(init_string)
    assert isinstance(result, InitData)
    assert result.auth_date == auth_date
    assert result.query_id == query_id
    assert result.user.model_dump() == user_data
    assert result.chat.model_dump() == chat_data
    assert result.ip == ip
    assert result.hash == hash_value
