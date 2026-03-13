# Frontend Dockerfile for AI Enablement Platform
# Multi-stage build for production optimization

# Stage 1: Build the React application
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies from lockfile (reproducible builds)
RUN npm ci

# Copy source code
COPY . .

# Accept build-time environment variables
# Default to empty string for production (uses relative URLs with nginx proxy)
ARG REACT_APP_API_URL=""
ARG REACT_APP_APPLETS="all"
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_APPLETS=$REACT_APP_APPLETS

# Build the application
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built application from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
