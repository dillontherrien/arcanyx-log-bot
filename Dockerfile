# Use an official Python runtime as a base image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements first to leverage caching
COPY requirements.txt /app/

# Install dependencies before copying the rest of the application files
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . /app

# Run the Python script
CMD ["python", "-u", "main.py"]
