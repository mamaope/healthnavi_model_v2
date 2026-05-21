# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN corepack enable && corepack prepare && pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Build the application
RUN pnpm run build

# Pre-compress static assets so nginx can serve them directly.
# This avoids CPU-heavy on-the-fly compression on small prod instances.
RUN find dist -type f \( \
  -name "*.js" -o \
  -name "*.css" -o \
  -name "*.html" -o \
  -name "*.svg" -o \
  -name "*.json" -o \
  -name "*.txt" -o \
  -name "*.xml" \
\) -exec gzip -k -9 {} \;

# Production stage
FROM nginx:alpine

# Copy built files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]


