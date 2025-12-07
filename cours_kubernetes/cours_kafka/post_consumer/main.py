import os
import json
import logging
from kafka import KafkaConsumer
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
KAFKA_HOST = os.getenv("KAFKA_HOST", "kafka-service:9092")
TOPIC = "posts"
GROUP_ID = "bq-consumer-group" # Important pour le scaling
DATASET_ID = os.getenv("DATASET_ID", "data_devops")
TABLE_ID = os.getenv("TABLE_ID", "posts")

# Auth BigQuery
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/service-account.json"

def main():
    log.info("Starting Consumer...")
    
    # Client BigQuery
    client = bigquery.Client()
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)
    
    # Consumer Kafka
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[KAFKA_HOST],
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id=GROUP_ID,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    log.info(f"Listening on {TOPIC}...")

    for message in consumer:
        post = message.value
        log.info(f"Received post ID: {post.get('id')}")

        # Insertion dans BigQuery (Streaming insert)
        errors = client.insert_rows_json(table_ref, [post])
        
        if errors == []:
            log.info(f"Inserted post {post.get('id')} into BigQuery")
        else:
            log.error(f"Errors inserting rows: {errors}")

if __name__ == "__main__":
    main()