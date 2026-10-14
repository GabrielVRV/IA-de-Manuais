# syntax=docker/dockerfile:1

# ---------- Estágio 1: build da tela ----------
FROM node:24-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------- Estágio 2: nginx servindo a tela e repassando /api/ para a API ----------
FROM nginx:stable-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# A API responde no mesmo endereço da tela (o nginx repassa /api/), então o cookie de
# login funciona sem CORS. O .htaccess só serve para o Apache do XAMPP.
RUN echo '{ "apiBaseUrl": "" }' > /usr/share/nginx/html/config.json \
    && rm -f /usr/share/nginx/html/.htaccess

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1
