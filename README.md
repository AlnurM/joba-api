# FastAPI MongoDB Project

Простой проект на FastAPI с использованием MongoDB.

## Требования

- Python 3.8+
- MongoDB
- pip (менеджер пакетов Python)

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
.\venv\Scripts\activate  # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Убедитесь, что MongoDB запущена на вашей машине

## Запуск

1. Запустите сервер:
```bash
uvicorn main:app --reload
```

2. Откройте браузер и перейдите по адресу: http://localhost:8000

3. Документация API доступна по адресу: http://localhost:8000/docs 