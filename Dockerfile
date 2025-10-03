# Step 1: Start with an official Python 3.13 "slim" operating system.
FROM python:3.13-slim

# Set environment variables to make sure installations run smoothly
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Step 2: Install build tools and Google Chrome in a single layer for efficiency
RUN apt-get update && apt-get install -y curl gnupg build-essential python3-dev \
    && curl -sS https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Step 3: Set up a working directory for our app inside the environment.
WORKDIR /app

# Step 4: Copy the requirements file and install all Python libraries.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy the rest of your application's code (app.py, etc.) into the environment.
COPY . .

# Step 6: Define the final command to run when the server starts.
CMD ["streamlit", "run", "app.py", "--server.headless", "true"]