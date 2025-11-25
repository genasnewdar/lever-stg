FROM python:3.13-slim

ARG ENV
ENV ENV=${ENV}

# Ensure output is flushed immediately to logs (Critical for debugging)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate prisma client
RUN python -m prisma generate

# Do not use 'exec' here if you want variable expansion for ${PORT}
# valid shell form:
CMD uvicorn app.server:app --host 0.0.0.0 --port ${PORT:-8080}