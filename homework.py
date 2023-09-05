import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (JsonFormatError, MessageSentError, RequestError,
                        StatusHomeworkError, VaribleError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
format = '%(asctime)s, %(levelname)s, %(lineno)s, %(message)s, %(name)s'
formatter = logging.Formatter(format)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    for variable in (PRACTICUM_TOKEN,
                     TELEGRAM_TOKEN,
                     TELEGRAM_CHAT_ID,
                     ENDPOINT):
        if variable is None:
            logger.critical(f'Переменная {variable} не доступна')
            return False
        elif not variable:
            logger.critical(f'Переменная {variable} пустая')
            return False
        return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug(f'Бот отправил сообщение - {message}')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения - {error}')
        raise MessageSentError(f'Ошибка при отправке сообщения - {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=payload)
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка запроса: {error}')
        raise RequestError(f'Ошибка запроса - {error}')
    except Exception as error:
        logger.error(f'Сбой при запросе к эндпоинту: {error}')
        raise RequestError(f'Сбой при запросе к эндпоинту - {error}')
    if response.status_code != 200:
        logger.error(f'Статус запроса: {response.status_code}')
        raise RequestError(f'Статус запроса - {response.status_code}')
    try:
        return response.json()
    except Exception as error:
        logger.error(f'Получен формат отличный от json: {error}')
        raise JsonFormatError(f'Ошибка формата - {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Структура данных ответа API не соответствует ожиданиям')
        raise TypeError('Структура данных не соответствует ожиданиям')
    if 'homeworks' in response:
        if isinstance(response['homeworks'], list):
            if response['homeworks']:
                return response['homeworks'][0]
            else:
                logger.error('"homeworks" - пустой список')
                raise IndexError('Список пустой')
        else:
            logger.error('Ключ "homeworks" не является списком')
            raise TypeError('Ключ "homeworks" не является списком')
    else:
        logger.error('В ответе API нет ключа "homeworks"')
        raise KeyError('В ответе API нет ключа "homeworks"')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework["homework_name"]
        status = homework["status"]
    except Exception:
        logger.error('Отсутсвует ключ словаря')
        raise KeyError('Отсутсвует ключ словаря')
    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logger.error('Недокументированный статус домашней работы')
    raise StatusHomeworkError('Недокументированный статус домашней работы')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise VaribleError('Переменные окружения не доступны')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
        except IndexError:
            message = 'Статус работы не изменился'
            send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
