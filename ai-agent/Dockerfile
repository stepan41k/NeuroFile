# --- Базовый образ с Python ---
FROM python:3.11-slim

# --- Рабочая директория внутри контейнера ---
WORKDIR /app

# --- Копируем файлы зависимостей ---
COPY requirements.txt .

# --- Устанавливаем зависимости ---
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- Копируем код приложения ---
COPY . .

# --- Экспорт порта (тот, который uvicorn будет слушать) ---
EXPOSE 3001

# --- Команда запуска приложения ---
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]