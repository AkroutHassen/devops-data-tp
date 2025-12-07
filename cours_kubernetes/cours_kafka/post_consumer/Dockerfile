FROM python:3.9.20-slim-bookworm

RUN pip install google-cloud-bigquery kafka-python
ENV PYTHONUNBUFFERED=1

# On copie le code
COPY ./post_consumer/main.py /app/main.py

# On s'attend à ce que le service-account soit monté via un volume K8s, 
# mais pour le build on prépare le dossier
WORKDIR /app

CMD ["python", "main.py"]