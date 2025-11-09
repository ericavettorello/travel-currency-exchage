import sys
import requests
from dotenv import load_dotenv
import os
from colorama import Fore, Style

# Устанавливаем кодировку UTF-8 для вывода в консоль Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Загружаем переменные окружения
load_dotenv()


def get_request(url, headers=None, params=None, timeout=30):
    """
    Выполняет GET запрос к указанному URL.
    
    Args:
        url (str): URL для запроса
        headers (dict, optional): Заголовки запроса
        params (dict, optional): Параметры запроса (query string)
        timeout (int, optional): Таймаут запроса в секундах (по умолчанию 30)
    
    Returns:
        dict: Словарь с результатом запроса:
            - 'success' (bool): Успешность запроса
            - 'data' (dict/list): Данные ответа (если успешно)
            - 'status_code' (int): HTTP статус код
            - 'error' (str): Сообщение об ошибке (если есть)
    """
    try:
        print(f"{Fore.CYAN}Выполняю GET запрос: {url}{Style.RESET_ALL}")
        
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()  # Вызовет исключение для статусов 4xx и 5xx
        
        data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        
        print(f"{Fore.GREEN}✓ GET запрос успешен. Статус: {response.status_code}{Style.RESET_ALL}")
        
        return {
            'success': True,
            'data': data,
            'status_code': response.status_code,
            'error': None
        }
    
    except requests.exceptions.Timeout:
        error_msg = f"Таймаут запроса (превышено {timeout} секунд)"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': None,
            'error': error_msg
        }
    
    except requests.exceptions.ConnectionError:
        error_msg = "Ошибка подключения к серверу"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': None,
            'error': error_msg
        }
    
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP ошибка: {e.response.status_code} - {e.response.reason}"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': e.response.status_code,
            'error': error_msg
        }
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка запроса: {str(e)}"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': None,
            'error': error_msg
        }


def post_request(url, data=None, json=None, headers=None, timeout=30):
    """
    Выполняет POST запрос к указанному URL.
    
    Args:
        url (str): URL для запроса
        data (dict, optional): Данные для отправки (form-data)
        json (dict, optional): JSON данные для отправки
        headers (dict, optional): Заголовки запроса
        timeout (int, optional): Таймаут запроса в секундах (по умолчанию 30)
    
    Returns:
        dict: Словарь с результатом запроса:
            - 'success' (bool): Успешность запроса
            - 'data' (dict/list): Данные ответа (если успешно)
            - 'status_code' (int): HTTP статус код
            - 'error' (str): Сообщение об ошибке (если есть)
    """
    try:
        print(f"{Fore.CYAN}Выполняю POST запрос: {url}{Style.RESET_ALL}")
        
        # Если передан json, устанавливаем соответствующий заголовок
        if json and not headers:
            headers = {'Content-Type': 'application/json'}
        elif json and headers:
            headers['Content-Type'] = 'application/json'
        
        response = requests.post(url, data=data, json=json, headers=headers, timeout=timeout)
        response.raise_for_status()  # Вызовет исключение для статусов 4xx и 5xx
        
        data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        
        print(f"{Fore.GREEN}✓ POST запрос успешен. Статус: {response.status_code}{Style.RESET_ALL}")
        
        return {
            'success': True,
            'data': data,
            'status_code': response.status_code,
            'error': None
        }
    
    except requests.exceptions.Timeout:
        error_msg = f"Таймаут запроса (превышено {timeout} секунд)"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': None,
            'error': error_msg
        }
    
    except requests.exceptions.ConnectionError:
        error_msg = "Ошибка подключения к серверу"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': None,
            'error': error_msg
        }
    
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP ошибка: {e.response.status_code} - {e.response.reason}"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': e.response.status_code,
            'error': error_msg
        }
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка запроса: {str(e)}"
        print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
        return {
            'success': False,
            'data': None,
            'status_code': None,
            'error': error_msg
        }


if __name__ == "__main__":
    # Пример использования функций
    print(f"{Fore.YELLOW}Функции для GET и POST запросов готовы к использованию!{Style.RESET_ALL}")
    
    # Пример GET запроса
    # result = get_request("https://api.example.com/data")
    # if result['success']:
    #     print(result['data'])
    
    # Пример POST запроса
    # result = post_request("https://api.example.com/data", json={"key": "value"})
    # if result['success']:
    #     print(result['data'])
