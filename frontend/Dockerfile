FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

EXPOSE 5173
# Development image (used by docker-compose). Production builds are served by Vercel.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
