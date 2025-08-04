# backend/Dockerfile
# Specifies the environment for the backend service.

# STRATEGY CHANGE: Use the full python:3.11-bookworm image.
# This image is larger but includes the build-essential tools
# required by ortools, which avoids the failing apt-get command.
FROM python:3.11-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Command to run the application
# 1. Run the seed script to ensure the database is initialized.
# 2. Start the Flask application using Gunicorn.
CMD ["sh", "-c", "python seed_demo.py && gunicorn --bind 0.0.0.0:8000 api:app"]
