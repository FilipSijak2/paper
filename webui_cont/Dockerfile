# Web UI build (Robo-boy integrated)
# Stage 1: Build React application
FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies
COPY package*.json ./
# Prefer npm ci for reproducible builds; fall back to install if lock is absent
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copy source
COPY . .

# Build with build args (ROSBRIDGE URL)
ARG VITE_ROSBRIDGE_URL=ws://localhost:9090
ENV VITE_ROSBRIDGE_URL=$VITE_ROSBRIDGE_URL
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Provide explicit root + index; add small /healthz endpoint; enable caching for static assets
RUN printf 'server {\n  listen 80;\n  server_name _;\n  root /usr/share/nginx/html;\n  index index.html;\n  add_header Cache-Control "public,max-age=604800";\n  location /healthz { return 200 "ok"; add_header Content-Type text/plain; }\n  location / { try_files $uri $uri/ /index.html; }\n  error_page 500 502 503 504 /50x.html;\n  location = /50x.html { return 500 "internal error"; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
