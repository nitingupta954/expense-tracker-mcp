# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory
WORKDIR /app

# Install uv (fast Python package installer)
RUN pip install uv

# Copy the dependencies file
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application code
COPY . .

# Sync the project itself
RUN uv sync --frozen --no-dev

# Expose the port the app runs on
EXPOSE 8000

# Set the transport to Server-Sent Events (SSE) for cloud deployment
# The DATABASE_URL environment variable must be provided by the cloud host
CMD ["uv", "run", "fastmcp", "run", "src/expense_tracker_mcp_server/server.py", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]
