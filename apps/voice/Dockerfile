FROM node:22-alpine
WORKDIR /app
COPY apps/voice/package.json ./
RUN npm install --omit=dev
COPY apps/voice ./
EXPOSE 3001
CMD ["npm", "start"]
