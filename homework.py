import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

logging.basicConfig(
    filename='program.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

TIMEOUT = 10
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class ApiCodeError(Exception):  # Можно сделать отдельный файл с исключениями?
    """Исключение для ошибок с API."""

    def __init__(self, message="Ошибка доступа к API"):
        super().__init__(message)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    result_message = []
    tokens = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
              'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
              'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    for token, value in tokens.items():
        if value is None:
            result_message.append(
                f"Недостаточно одной из главных"
                f"переменных из окружения '{token}'"
            )
    return result_message


def send_message(bot, message):
    """Отправка сообщений в Telegram-чат."""
    logging.debug('Отправка сообщения в чат.')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Отправка сообщения завершена.')
    except Exception:
        logging.error('Сообщение не доставлено, произошел сбой.')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=TIMEOUT
        )
    except requests.exceptions.RequestException:
        raise ApiCodeError('API недоступно')
    if response.status_code == HTTPStatus.OK:
        logging.info('API доступно')
        try:
            response = response.json()
            logging.info('Данные успешно получены')
            return response
        except json.decoder.JSONDecodeError:
            message = 'Ошибка получения данных'
            raise json.decoder.JSONDecodeError(f'{message}')
    raise ApiCodeError


def check_response(response):
    """Проверяет ответ API ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        raise KeyError("Ответ не содержит 'homeworks'")

    if not isinstance(response['homeworks'], list):
        raise TypeError("'homeworks' в ответе должен быть списком")

    return True


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе.
    Cтатус этой работы.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None:
        raise ValueError(
            "Отсутствует ключ 'homework_name' в словаре homework."
        )
    if homework_status is None:
        raise ValueError("Отсутствует ключ 'status' в словаре homework.")

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неверный статус домашней работы: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logging.critical('Токены не прошли валидацию')
        sys.exit('Ошибка: Токены не прошли валидацию')
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = 0
    last_status = None

    while True:
        try:
            api_response = get_api_answer(timestamp)
            if check_response(api_response):
                if not api_response['homeworks']:
                    logging.debug('Получен пустой список с домашним заданием')
                else:
                    last_homework = api_response['homeworks'][0]
                    current_status = parse_status(last_homework)
                    if last_status != current_status:
                        send_message(bot, current_status)
                        last_status = current_status
            timestamp = int(time.time())
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
