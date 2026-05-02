FROM node:20-alpine

WORKDIR /app

# Copy package files first (layer caching)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy rest of code
COPY . .

EXPOSE 5173

# --host 0.0.0.0 is critical — without this Docker can't expose the port
CMD ["npm", "run", "dev"]