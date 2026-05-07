FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy server code
COPY . .

# Expose MCP server
CMD ["node", "index.js"]
