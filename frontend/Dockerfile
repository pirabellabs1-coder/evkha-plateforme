# Stage 1 — build React/Vite
FROM node:20-alpine AS builder
WORKDIR /app
# Copier les manifestes en premier pour profiter du cache Docker
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/index.html frontend/vite.config.ts frontend/vite.prerendu.config.ts ./
COPY frontend/tsconfig*.json ./
COPY frontend/public ./public
COPY frontend/src ./src
# Le pré-rendu des pages publiques, lancé par `npm run build` après Vite :
# il écrit un fichier HTML par page, `sitemap.xml`, `robots.txt` et `llms.txt`.
COPY frontend/scripts ./scripts
RUN npm run build

# Stage 2 — servir avec nginx
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
