# Use Python 3.12.8 base image
FROM python:3.12.8

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install system dependencies (including setuptools)
RUN pip install --no-cache-dir --upgrade pip setuptools

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 5050

# Start the Flask app
CMD ["python", "app.py"]
