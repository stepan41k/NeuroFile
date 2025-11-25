# Stage 1: Build
FROM node:18-alpine as builder

WORKDIR /app

# Копируем конфиги
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем исходный код
COPY . .

# Собираем Vite проект (результат будет в /app/dist)
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Удаляем дефолтный конфиг Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Копируем наш конфиг Nginx (создадим его ниже)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Копируем собранную статику из Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]