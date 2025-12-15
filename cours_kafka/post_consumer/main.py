import os
import json
import logging

from kafka import KafkaConsumer
from google.cloud import bigquery
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Config via env vars (avec valeurs par défaut pour le TP) -----------------

KAFKA_HOST = os.getenv("KAFKA_HOST", "kafka-broker-service.cours-kubernetes:9092")
TOPIC = os.getenv("TOPIC", "posts")
GROUP_ID = os.getenv("GROUP_ID", "bq-consumer-group")  # important pour le scaling

DATASET_ID = os.getenv("DATASET_ID", "data_devops")
TABLE_ID = os.getenv("TABLE_ID", "posts")

# MongoDB (StatefulSet in the Kubernetes cluster)
MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb.cours-kubernetes.svc.cluster.local")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_USER = os.getenv("MONGODB_USER", "root")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "change-me")
MONGODB_DB = os.getenv("MONGODB_DB", "data_devops")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "posts")


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


def create_mongo_collection():
    """Creates MongoDB collection used for the double-write."""
    mongo_uri = (
        f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/"
        "?authSource=admin"
    )
    log.info(f"Connecting to MongoDB at {MONGODB_HOST}:{MONGODB_PORT}, db={MONGODB_DB}")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB]
    col = db[MONGODB_COLLECTION]

    # Best-effort index for idempotent upsert; failures should not crash the consumer.
    try:
        col.create_index("id", unique=True)
    except PyMongoError:
        log.exception("Failed to create MongoDB index; continuing without it")

    return col


def normalize_post(post: dict) -> dict:
    """Normalise the message structure for Mongo upsert (ensure 'id' exists)."""
    post_id = post.get("id") or post.get("Id")
    if post_id is not None:
        post["id"] = str(post_id)
    return post


def main():
    log.info("Starting Kafka → BigQuery + MongoDB consumer...")

    client, table_ref = create_bq_client()
    mongo_col = create_mongo_collection()
    consumer = create_consumer()

    log.info(f"Listening on topic '{TOPIC}'...")

    for message in consumer:
        post = normalize_post(message.value)

        # Dans posts.json, la clé est souvent "Id" (majuscule) → on gère les deux
        post_id = post.get("id")

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

        # Double-write to MongoDB (idempotent upsert)
        if post_id:
            try:
                mongo_col.update_one({"id": post_id}, {"$set": post}, upsert=True)
                log.info(f"Upserted post {post_id} into MongoDB")
            except PyMongoError:
                log.exception("Error writing into MongoDB")
        else:
            log.warning("Skipping MongoDB write: missing post id")


if __name__ == "__main__":
    main()