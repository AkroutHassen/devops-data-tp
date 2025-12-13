import os
import json
import logging

from kafka import KafkaConsumer
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Config via env vars (avec valeurs par défaut pour le TP) -----------------

KAFKA_HOST = os.getenv("KAFKA_HOST", "kafka-broker-service.cours-kubernetes:9092")
TOPIC = os.getenv("TOPIC", "posts")
GROUP_ID = os.getenv("GROUP_ID", "bq-consumer-group")  # important pour le scaling

DATASET_ID = os.getenv("DATASET_ID", "data_devops")
TABLE_ID = os.getenv("TABLE_ID", "posts")


def create_bq_client():
    """Crée un client BigQuery et renvoie (client, table_ref)."""
    log.info(f"GOOGLE_APPLICATION_CREDENTIALS={os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
    client = bigquery.Client()
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)
    log.info(f"Using BigQuery table: {client.project}.{DATASET_ID}.{TABLE_ID}")
    return client, table_ref


def create_consumer():
    """Crée le consumer Kafka."""
    log.info(
        f"Creating Kafka consumer on topic='{TOPIC}', "
        f"bootstrap_servers='{KAFKA_HOST}', group_id='{GROUP_ID}'"
    )

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[KAFKA_HOST],
        auto_offset_reset="earliest",      # lit depuis le début au premier lancement
        enable_auto_commit=True,
        group_id=GROUP_ID,
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    return consumer


def main():
    log.info("Starting Kafka → BigQuery consumer...")

    client, table_ref = create_bq_client()
    consumer = create_consumer()

    log.info(f"Listening on topic '{TOPIC}'...")

    for message in consumer:
        post = message.value

        # Dans posts.json, la clé est souvent "Id" (majuscule) → on gère les deux
        post_id = post.get("Id") or post.get("id")

        log.info(
            f"Received message from Kafka: post_id={post_id}, "
            f"partition={message.partition}, offset={message.offset}"
        )

        # Streaming insert BigQuery
        errors = client.insert_rows_json(table_ref, [post])

        if not errors:
            log.info(f"Inserted post {post_id} into BigQuery")
        else:
            log.error(f"Error inserting into BigQuery: {errors}")


if __name__ == "__main__":
    main()