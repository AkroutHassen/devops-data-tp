FROM python:3.9.20-slim-bookworm

RUN pip install google-cloud-bigquery "fastapi[standard]"
ENV PYTHONUNBUFFERED=1

COPY ./service-account.json ./service-account.json
COPY ./post_api/ ./
CMD [ "python", "main.py"]