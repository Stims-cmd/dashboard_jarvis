# Frontend image. Targets:
#   dev  -> Vite dev server, code mounted as a volume
#   prod -> static build served by nginx, which also proxies /api (default)
FROM node:24-alpine AS dev
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci
EXPOSE 5173
CMD ["npx", "vite", "--host", "0.0.0.0"]

FROM dev AS build
COPY --chown=node:node . .
RUN npm run build

FROM nginx:1.30-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
