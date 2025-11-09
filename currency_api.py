import sys
import requests
from dotenv import load_dotenv
import os
from main import get_request

# Устанавливаем кодировку UTF-8 для вывода в консоль Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Загружаем переменные окружения
load_dotenv()

# Список поддерживаемых валют exchangerate.host (168 валют)
SUPPORTED_CURRENCIES = [
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
    "BSD", "BTC", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHF", "CLF",
    "CLP", "CNY", "COP", "CRC", "CUC", "CUP", "CVE", "CZK", "DJF", "DKK",
    "DOP", "DZD", "EGP", "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL",
    "GGP", "GHS", "GIP", "GMD", "GNF", "GTQ", "GYD", "HKD", "HNL", "HRK",
    "HTG", "HUF", "IDR", "ILS", "IMP", "INR", "IQD", "IRR", "ISK", "JEP",
    "JMD", "JOD", "JPY", "KES", "KGS", "KHR", "KMF", "KPW", "KRW", "KWD",
    "KYD", "KZT", "LAK", "LBP", "LKR", "LRD", "LSL", "LYD", "MAD", "MDL",
    "MGA", "MKD", "MMK", "MNT", "MOP", "MRO", "MUR", "MVR", "MWK", "MXN",
    "MYR", "MZN", "NAD", "NGN", "NIO", "NOK", "NPR", "NZD", "OMR", "PAB",
    "PEN", "PGK", "PHP", "PKR", "PLN", "PYG", "QAR", "RON", "RSD", "RUB",
    "RWF", "SAR", "SBD", "SCR", "SDG", "SEK", "SGD", "SHP", "SLL", "SOS",
    "SRD", "STD", "SVC", "SYP", "SZL", "THB", "TJS", "TMT", "TND", "TOP",
    "TRY", "TTD", "TWD", "TZS", "UAH", "UGX", "USD", "UYU", "UZS", "VEF",
    "VND", "VUV", "WST", "XAF", "XAG", "XAU", "XCD", "XDR", "XOF", "XPF",
    "YER", "ZAR", "ZMK", "ZMW", "ZWL"
]


def get_current_currency(default="RUB", currencies=None):
    """
    Получает текущий курс валют из API exchangerate.host.
    
    Args:
        default (str): Базовая валюта (по умолчанию RUB)
        currencies (list, optional): Список валют для получения курса.
                                    Если None, используется ["USD", "EUR", "GBP", "JPY"].
    
    Returns:
        dict: Ответ от API exchangerate.host с данными о курсах валют
    """
    # Используем API exchangerate.host
    # Документация: https://exchangerate.host/
    url = os.getenv("CURRENCY_API_URL", "https://api.exchangerate.host/live")
    
    # Если список валют не указан, используем значения по умолчанию
    if currencies is None:
        currencies = ["USD", "EUR", "GBP", "JPY"]
    
    # Получаем API ключ из переменных окружения (если требуется)
    access_key = os.getenv("CURRENCY_API_KEY")
    
    # Формируем параметры запроса
    params = {
        "source": default,
        "currencies": ",".join(currencies)  # ",".join(currencies) означает объединение в строку с разделителем-запятой
    }
    
    # Добавляем access_key только если он указан
    if access_key:
        params["access_key"] = access_key
    
    result = get_request(url, params=params)
    
    if not result['success']:
        return {
            'success': False,
            'error': result['error']
        }
    
    # Возвращаем данные напрямую, как в примере пользователя
    return result['data']


def get_currency_rate(from_currency, to_currency):
    """
    Получает курс обмена между двумя валютами.
    
    Args:
        from_currency (str): Исходная валюта (например, 'USD')
        to_currency (str): Целевая валюта (например, 'EUR')
    
    Returns:
        dict: Ответ от API с данными о курсе обмена
    """
    result = get_current_currency(default=from_currency, currencies=[to_currency])
    return result


def get_supported_currencies():
    """
    Получает список поддерживаемых валют от API exchangerate.host.
    
    Returns:
        dict: Ответ от API с данными о поддерживаемых валютах:
            - 'success' (bool): Успешность запроса
            - 'currencies' (dict): Словарь с кодами валют и их названиями
            - 'error' (str): Сообщение об ошибке (если есть)
    """
    # Используем API exchangerate.host для получения списка валют
    # Документация: https://exchangerate.host/
    url = "https://api.exchangerate.host/list"
    
    # Получаем API ключ из переменных окружения
    access_key = os.getenv("CURRENCY_API_KEY")
    
    # Формируем параметры запроса
    params = {}
    
    # Добавляем access_key только если он указан
    if access_key:
        params["access_key"] = access_key
    
    result = get_request(url, params=params)
    
    if not result['success']:
        return {
            'success': False,
            'currencies': None,
            'error': result['error']
        }
    
    # Возвращаем данные от API
    data = result['data']
    
    # Если API вернул успешный ответ
    if data.get('success', False):
        return {
            'success': True,
            'currencies': data.get('currencies', {}),
            'error': None
        }
    else:
        return {
            'success': False,
            'currencies': None,
            'error': data.get('error', 'Ошибка при получении списка валют')
        }


def convert_currency(from_currency, to_currency, amount):
    """
    Конвертирует сумму из одной валюты в другую.
    
    Args:
        from_currency (str): Исходная валюта (например, 'USD')
        to_currency (str): Целевая валюта (например, 'GBP')
        amount (float): Сумма для конвертации
    
    Returns:
        dict: Ответ от API с результатом конвертации:
            - 'success' (bool): Успешность запроса
            - 'query' (dict): Параметры запроса (from, to, amount)
            - 'info' (dict): Информация о курсе (rate, timestamp)
            - 'result' (float): Результат конвертации
            - 'error' (str): Сообщение об ошибке (если есть)
    """
    # Используем API exchangerate.host для конвертации
    # Документация: https://exchangerate.host/
    url = "http://api.exchangerate.host/convert"
    
    # Получаем API ключ из переменных окружения
    access_key = os.getenv("CURRENCY_API_KEY")
    
    # Формируем параметры запроса
    params = {
        "from": from_currency,
        "to": to_currency,
        "amount": amount
    }
    
    # Добавляем access_key только если он указан
    if access_key:
        params["access_key"] = access_key
    
    result = get_request(url, params=params)
    
    if not result['success']:
        return {
            'success': False,
            'query': {'from': from_currency, 'to': to_currency, 'amount': amount},
            'info': None,
            'result': None,
            'error': result['error']
        }
    
    # Возвращаем данные от API
    data = result['data']
    
    # Если API вернул успешный ответ
    if data.get('success', False):
        return {
            'success': True,
            'query': data.get('query', {'from': from_currency, 'to': to_currency, 'amount': amount}),
            'info': data.get('info', {}),
            'result': data.get('result'),
            'error': None
        }
    else:
        return {
            'success': False,
            'query': {'from': from_currency, 'to': to_currency, 'amount': amount},
            'info': None,
            'result': None,
            'error': data.get('error', 'Ошибка при конвертации валют')
        }


if __name__ == "__main__":
    # Пример использования
    print("Получение текущих курсов валют:")
    print(get_current_currency())
    
    print("\n" + "="*50)
    print("Пример конвертации валют:")
    result = convert_currency("USD", "GBP", 10)
    if result['success']:
        print(f"{result['query']['amount']} {result['query']['from']} = {result['result']} {result['query']['to']}")
        print(f"Курс: {result['info'].get('rate', 'N/A')}")
    else:
        print(f"Ошибка: {result['error']}")
    
    print("\n" + "="*50)
    print("Получение списка поддерживаемых валют:")
    currencies_result = get_supported_currencies()
    if currencies_result['success']:
        currencies = currencies_result['currencies']
        print(f"Всего валют: {len(currencies)}")
        print("\nПервые 20 валют:")
        for i, (code, name) in enumerate(list(currencies.items())[:20], 1):
            print(f"{i}. {code}: {name}")
    else:
        print(f"Ошибка: {currencies_result['error']}")
