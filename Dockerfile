FROM python:3.13-slim

ARG ENV
ENV ENV=${ENV}

COPY . .

RUN pip install -r requirements.txt
RUN prisma generate

EXPOSE 8080

CMD exec uvicorn app.server:app --host 0.0.0.0 --port 8080