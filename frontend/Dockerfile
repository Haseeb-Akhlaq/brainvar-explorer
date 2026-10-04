# Production image: build the React app, then serve the static output with
# nginx. The outer reverse proxy handles TLS and routes /api/ to Django, so
# this container only serves files.

# --- build ------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Empty means "same origin": the app calls /api/... and the reverse proxy
# routes it to Django. Set this only if the API lives on another host.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# --- serve ------------------------------------------------------------------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
