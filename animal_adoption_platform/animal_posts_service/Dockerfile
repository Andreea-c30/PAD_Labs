# animal_posts_service/Dockerfile
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file if it exists
COPY requirements.txt ./
# If you don't have a requirements file, add dependencies in the next step.

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code to the container
COPY . .

# Expose the gRPC server port
EXPOSE 50052

# Command to run the application
CMD ["python", "server.py"]
