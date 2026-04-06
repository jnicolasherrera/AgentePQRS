FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG NEXT_PUBLIC_API_URL=https://app.flexpqr.com
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Tratamos de hacer el build, si el usuario tiene errores de tailwind, esto le mostrará la salida.
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
