# ⚠️ CHƯA KIỂM CHỨNG — Docker không có trên máy phát triển. Xem README.
#
# Build context là GỐC repo (không phải apps/web) vì package-lock.json nằm ở
# gốc do dùng npm workspaces.

FROM node:22-alpine AS builder

WORKDIR /repo

# Copy manifest trước để layer cài dependency được cache lại khi chỉ sửa code.
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
RUN npm ci

COPY apps/web ./apps/web
RUN npm run build --workspace=apps/web


FROM nginx:alpine AS runtime

COPY --from=builder /repo/apps/web/dist /usr/share/nginx/html
COPY infrastructure/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1
