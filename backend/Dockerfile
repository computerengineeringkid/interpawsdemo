# backend/Dockerfile
# Specifies the environment for the backend service.

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
# 2. Start the FastAPI application using Gunicorn, pointing to the correct module.
CMD ["sh", "-c", "python -m app.seed_demo && gunicorn --bind 0.0.0.0:8000 app.main:app -k uvicorn.workers.UvicornWorker"]