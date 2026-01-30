FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system deps (needed for mysql client libs)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot
COPY . .

# Run the bot
CMD ["python", "PUBobot2.py"]
