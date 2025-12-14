FROM python:3.9.20-slim-bookworm

RUN pip install google-cloud-bigquery kafka-python importlib-metadata
ENV PYTHONUNBUFFERED=1

COPY ./post_pusher/ /app/
WORKDIR /app

CMD ["python", "main.py"]