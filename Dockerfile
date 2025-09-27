# Step 1: Start with an official Python 3.13 "slim" operating system.
# This is a lightweight version of Linux with Python pre-installed.
FROM python:3.13-slim

# Set environment variables to make sure installations run smoothly
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Step 2: Install Google Chrome. This is the fix for the Kaleido error.
# These commands run as the administrator (root) inside the build environment.
RUN apt-get update && apt-get install -y wget gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# Step 3: Set up a working directory for our app inside the environment.
WORKDIR /app

# Step 4: Copy the requirements file and install all Python libraries.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy the rest of your application's code (app.py, etc.) into the environment.
COPY . .

# Step 6: Define the final command to run when the server starts.
# This tells Render how to launch your Streamlit app.
CMD ["streamlit", "run", "app.py", "--server.headless", "true"]