# Используем легкий образ Node.js
FROM node:18-alpine

# Рабочая директория внутри контейнера
WORKDIR /app

# Сначала копируем package.json, чтобы кэшировать установку модулей
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install --production
RUN npm install form-data

# Копируем остальной код
COPY . .

# Создаем папки для данных внутри контейнера (на случай, если volumes не примонтированы)
RUN mkdir -p uploads data

# Открываем порт
EXPOSE 3000

# Команда запуска
CMD ["npm", "start"]