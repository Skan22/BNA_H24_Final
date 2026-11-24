FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# L'adresse de l'API est figée à la construction (réécriture /api -> API).
ARG BOUSSOLA_API=http://api:8000
ENV BOUSSOLA_API=$BOUSSOLA_API
RUN npx next build
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
