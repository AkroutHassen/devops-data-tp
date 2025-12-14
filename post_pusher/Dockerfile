FROM python:3.9.20-slim-bookworm

RUN pip install google-cloud-bigquery kafka-python
ENV PYTHONUNBUFFERED=1

COPY ./post_pusher/ ./
CMD ["python", "main.py"]