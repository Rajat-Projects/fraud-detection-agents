# Stage 1 — Build React app
# node:20-alpine keeps the build image small; no Node.js in the final image.
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first — separate layer so npm ci is only re-run when
# dependencies change, not on every source file change.
COPY package*.json ./
RUN npm ci --silent

# Copy source and build
COPY . .

# Rule D5: VITE_ prefix required for Vite to expose env vars to the browser.
# Build arg so Railway/Vercel can inject the production API URL at build time.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2 — Serve with nginx
# Final image contains only nginx + static files. No Node.js, no npm, no source.
FROM nginx:alpine AS runtime

# Copy compiled React app from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx config: React Router support + security headers + gzip
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
