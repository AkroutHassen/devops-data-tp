FROM python:3.9.20-slim-bookworm

RUN pip install google-cloud-bigquery "fastapi[standard]" importlib-metadata
ENV PYTHONUNBUFFERED=1

COPY ./post_api/ /app/
WORKDIR /app

CMD [ "python", "main.py"]