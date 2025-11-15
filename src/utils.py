import hashlib
import hmac
import json
import tempfile
import urllib.parse

from PIL import Image, ImageDraw, ImageFont

from src.models import InitData

CERTIFICATE_IMAGE_PATH = 'assets/certificate.png'
FONT_FILE_PATH = 'assets/Montserrat.ttf'


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
    base_image = Image.open(CERTIFICATE_IMAGE_PATH).convert('RGBA')
    draw = ImageDraw.Draw(base_image)
    font = ImageFont.truetype(FONT_FILE_PATH, 36)

    certificate_text = (
        f'Сертификат подтверждает, что {user_name}\n'
        'прошёл игру “Инклюзивный конструктор” и\n'
        'внёс вклад в создание города, удобного и\n'
        'открытого для всех.\n\n'
        f'Уровень доступности достигнут: {user_score:.0f}%\n'
        'Присвоено звание: Архитектор без барьеров'
    )

    text_area_x = 164
    text_area_y = 344
    text_area_width = 862

    raw_lines = certificate_text.split('\n')
    final_lines = []

    for raw_line in raw_lines:
        if raw_line.strip() == '':
            final_lines.append('')
            continue

        words = raw_line.split(' ')
        current_line = ''

        for word in words:
            test_line = word if not current_line else current_line + ' ' + word
            if draw.textlength(test_line, font=font) <= text_area_width:
                current_line = test_line
            else:
                final_lines.append(current_line)
                current_line = word

        if current_line:
            final_lines.append(current_line)

    line_height = font.getbbox('A')[3] - font.getbbox('A')[1] + 22
    offset_y = text_area_y

    for line in final_lines:
        if line:
            draw.text((text_area_x, offset_y), line, font=font, fill=(0, 0, 0))

        offset_y += line_height

    tmp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    base_image.save(tmp_file.name)
    return tmp_file.name
