FROM python:3.13-slim

ARG ENV
ENV ENV=${ENV}

WORKDIR /app          # good practice so prisma runs in the project root

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use module form – same thing, a bit more reliable
RUN python -m prisma generate

EXPOSE 8080

CMD exec uvicorn app.server:app --host 0.0.0.0 --port 8080
