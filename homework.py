import logging
import os
import sys
import time
from http import HTTPStatus
from json.decoder import JSONDecodeError

from dotenv import load_dotenv
import requests
import telegram
from telegram.error import TelegramError

from config import ENDPOINT

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    variables = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(variables)


def send_message(bot, message):
    """Отправляет сообщение об изменении статуса домашней работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except TelegramError as error:
        logger.error(error)
        raise error(f'Сообщение не отправлено, {error}')


def get_api_answer(timestamp):
    """Запрашивает ответ API."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
        if response.status_code == HTTPStatus.OK:
            logger.debug('Успешный запрос к API')
        else:
            raise Exception(f'Эндпоинт {ENDPOINT} недоступен.'
                            f'Код ответа API: {response.status_code}')
    except Exception as error:
        raise Exception(f'Сбой при запросе к эндпоинту: {error}')
    try:
        response.json()
    except JSONDecodeError:
        raise JSONDecodeError('Сбой при попытке преобразовать ответ в json')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответсвие документации."""
    if not isinstance(response, dict):
        raise TypeError('Данные не соответсвуют ожидаемому типу dict')
    if 'homeworks' not in response:
        raise KeyError('Отвутсвует необходимый ключ "homeworks"')
    homework_list = response['homeworks']
    if not isinstance(homework_list, list):
        raise TypeError('Данные не соответсвуют ожидаемому типу list')
    if len(homework_list) == 0:
        raise ValueError('Полученный список домашних заданий пуст')
    if not isinstance(homework_list[0], dict):
        raise TypeError('Данные не соответсвуют ожидаемому типу dict')
    return homework_list


def parse_status(homework):
    """Возвращает статус домашней работы."""
    homework_keys = ['homework_name', 'status']
    for key in homework_keys:
        if key not in homework:
            raise KeyError(f'Отсутствует ключ "{key}" в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Получен неизвестный статус "{homework_status}"'
                         f'у работы "{homework_name}"')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует обязательная переменная окружения . '
                        'Программа принудительно остановлена.')
        raise Exception
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework[0])
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logger.debug('Отсутсвуют изменения статуса')
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)
            if last_error_message != error_message:
                send_message(bot, error_message)
                last_error_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, %(message)s'
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()
