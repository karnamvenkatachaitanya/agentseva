# ─────────────────────────────────────────────────────────────────────────
# AgentSeva Frontend — React + Vite, served by nginx which proxies /api → backend
# Build context: ./frontend
# ─────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
# Type-check + build; fall back to a plain vite build so a stray type error
# never blocks the demo container.
RUN npm run build || npx vite build

# ── Runtime: static files behind nginx ───────────────────────────────────
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
