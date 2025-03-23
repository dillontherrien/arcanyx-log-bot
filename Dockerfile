# Use an official Python runtime as a base image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the Python script
CMD ["python", "-u", "main.py"]
