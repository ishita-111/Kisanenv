FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

EXPOSE 7860

# Run using uvicorn directly targeting the env app
CMD ["sh", "-c", "uvicorn env:app --host 0.0.0.0 --port $PORT"]