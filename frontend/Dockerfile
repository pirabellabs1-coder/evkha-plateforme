# Stage 1 — build React/Vite
FROM node:20-alpine AS builder
WORKDIR /app
# Copier les manifestes en premier pour profiter du cache Docker
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/index.html frontend/vite.config.ts ./
COPY frontend/tsconfig*.json ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

# Stage 2 — servir avec nginx
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
