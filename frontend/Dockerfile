# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./ 
COPY package-lock.json* ./

# Install dependencies
RUN npm ci --production=false || npm install

# Copy source
COPY . .

# Build
RUN npm run build

# Runner stage
FROM node:18-alpine AS runner

WORKDIR /app

# Install dumb-init
RUN apk add --no-cache dumb-init

# Copy from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public 2>/dev/null || true

# Environment
ENV NODE_ENV=production
EXPOSE 3000

# Entrypoint
ENTRYPOINT ["dumb-init", "--"]
CMD ["npm", "start"]
