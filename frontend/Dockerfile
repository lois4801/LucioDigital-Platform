FROM node:20-alpine AS build
WORKDIR /app/frontend
ARG REACT_APP_BACKEND_URL=
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY . .
RUN yarn build

FROM nginx:1.27-alpine
ENV BACKEND_HOST=backend:8001
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/build /usr/share/nginx/html
EXPOSE 80
