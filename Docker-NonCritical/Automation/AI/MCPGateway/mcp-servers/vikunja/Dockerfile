FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Install supergateway globally (no npx on every restart)
RUN npm install -g supergateway@3.4.3

# Copy server code
COPY . .

# Expose MCP server
CMD ["sh", "-c", "supergateway --port 3000 --outputTransport streamableHttp --stdio 'npx -y vikunja-mcp'"]
