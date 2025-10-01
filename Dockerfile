# ---------- FRONTEND BUILD STAGE ----------
FROM node:24-slim AS frontend-builder
WORKDIR /app

# Copy frontend dependencies
COPY nse-scheduler-frontend/package*.json ./
RUN npm install

# Copy frontend source and build
COPY nse-scheduler-frontend/ ./
RUN npm run build

# ---------- BACKEND STAGE ----------
FROM node:24-slim
WORKDIR /usr/src/app

# Backend dependencies
COPY package*.json ./
RUN npm install

# Copy backend source
COPY . .

# Copy frontend build into public folder
COPY --from=frontend-builder /app/build ./public

EXPOSE 5000
CMD ["node", "server.js"]
