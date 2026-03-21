FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build -- --configuration production

# Stage 2: Serve
FROM nginx:alpine
# Copy the build output to Nginx's serve directory
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
# Copy a custom nginx config if you have one to handle Angular routing
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]