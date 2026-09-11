FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public
EXPOSE 3000
# "next start" ya respeta la variable de entorno PORT automáticamente si está definida
# (Railway, etc.) y cae a 3000 si no existe (docker-compose local) -- no hace falta pasarle
# -p a mano. Se usa "npm start" (no "next" directo) porque npm agrega node_modules/.bin al
# PATH; llamar a "next" fuera de un script de npm/npx falla con "next: not found".
CMD ["npm", "start"]
