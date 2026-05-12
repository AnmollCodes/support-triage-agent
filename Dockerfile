FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt .
COPY code/ code/
COPY support_issues/ support_issues/
COPY .env.example .env

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create output directory
RUN mkdir -p output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ANTHROPIC_API_KEY=

# Run the agent by default
CMD ["python", "code/run_agent.py"]

# Expose port for API server (if using FastAPI mode)
EXPOSE 8000
