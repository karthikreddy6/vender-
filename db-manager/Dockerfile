# Use official lightweight Node.js image
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy the rest of the application files
COPY . .

# Expose port 8002 (default for the db manager)
EXPOSE 8002

# Start the node server
CMD ["node", "server.js"]
