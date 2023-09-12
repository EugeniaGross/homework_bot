import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (JsonFormatError, MessageSentError, RequestError,
                        StatusHomeworkError)

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    for variable in (PRACTICUM_TOKEN,
                     TELEGRAM_TOKEN,
                     TELEGRAM_CHAT_ID,):
        if variable is None:
            logging.critical(f'Переменная {variable} отсутствует')
            return False
        elif not variable:
            logging.critical(f'Переменная {variable} пустая')
            return False
        return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.debug('Начало отправки сообщения')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug(f'Бот отправил сообщение - {message}')
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения: {error}')
        raise MessageSentError(f'Ошибка при отправке сообщения - {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    logging.debug('Начало запроса к API')
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=payload)
    except requests.exceptions.RequestException as error:
        raise RequestError(f'Ошибка запроса - {error}')
    except Exception as error:
        raise RequestError(f'Сбой при запросе к эндпоинту - {error}')
    if response.status_code != 200:
        raise RequestError(f'Статус запроса - {response.status_code}')
    try:
        return response.json()
    except Exception as error:
        raise JsonFormatError(f'Ошибка формата - {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logging.debug('Начало проверки ответа сервера')
    if not isinstance(response, dict):
        raise TypeError(
            'Структура данных ответа API не соответствует ожиданиям'
        )
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ "homeworks" не является списком')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа "current_date"')
    return response


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logging.debug('Начало извлечения статуса домашней работы')
    if "homework_name" not in homework:
        raise KeyError('Отсутсвует ключ "homework_name"')
    if "status" not in homework:
        raise KeyError('Отсутсвует ключ "status"')
    homework_name = homework["homework_name"]
    status = homework["status"]
    if status not in HOMEWORK_VERDICTS:
        raise StatusHomeworkError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit('Переменные окружения не доступны')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    bot_message = ''
    error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            good_response = check_response(response)
            if good_response['homeworks']:
                message = parse_status(good_response['homeworks'][0])
            else:
                message = 'Статус работы не изменился'
            timestamp = good_response['current_date']
            if message != bot_message:
                send_message(bot, message)
                bot_message = message
        except MessageSentError(
            'Ошибка отправки сообщения в телеграмм'
        ):
            logging.error('Ошибка отправки сообщения в телеграмм')
        except Exception as error:
            logging.error(f'Ошибка в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(lineno)s, %(message)s, %(name)s',
        handlers=logging.StreamHandler(stream=sys.stdout)
    )
    main()
