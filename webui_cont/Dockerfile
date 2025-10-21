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
# Add basic nginx config to enable caching for static assets (optional)
RUN printf 'server {\n  listen 80;\n  add_header Cache-Control "public,max-age=604800";\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
# Basic health endpoint (optional future)
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
