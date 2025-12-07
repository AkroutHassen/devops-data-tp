import logging
import random
import os
import json
from google.cloud import bigquery
import re
import time
import argparse
from kafka import KafkaProducer


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOPIC = "posts"  # Name of the Kafka topic
SCHEMA = [  # Define the schema for the table
    bigquery.SchemaField('id', 'STRING', mode='REQUIRED'),
    bigquery.SchemaField('post_type_id', 'STRING', mode='REQUIRED'),
    bigquery.SchemaField('accepted_answer_id', 'STRING', mode='NULLABLE'),
    bigquery.SchemaField('creation_date', 'TIMESTAMP', mode='REQUIRED'),
    bigquery.SchemaField('score', 'INTEGER', mode='REQUIRED'),
    bigquery.SchemaField('view_count', 'INTEGER', mode='NULLABLE'),
    bigquery.SchemaField('body', 'STRING', mode='REQUIRED'),
    bigquery.SchemaField('owner_user_id', 'STRING', mode='NULLABLE'),
    bigquery.SchemaField('last_editor_user_id', 'STRING', mode='NULLABLE'),
    bigquery.SchemaField('last_edit_date', 'TIMESTAMP', mode='NULLABLE'),
    bigquery.SchemaField('last_activity_date', 'TIMESTAMP', mode='NULLABLE'),
    bigquery.SchemaField('title', 'STRING', mode='NULLABLE'),
    bigquery.SchemaField('tags', 'STRING', mode='NULLABLE'),
    bigquery.SchemaField('answer_count', 'INTEGER', mode='NULLABLE'),
    bigquery.SchemaField('comment_count', 'INTEGER', mode='REQUIRED'),
    bigquery.SchemaField('content_license', 'STRING', mode='REQUIRED'),
    bigquery.SchemaField('parent_id', 'STRING', mode='NULLABLE')
]

def create_dataset_if_not_exists(client, dataset_id, project_id):
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        client.get_dataset(dataset_ref)  # Make an API request.
        log.info(f"Dataset {dataset_id} already exists.")
    except Exception as e:
        log.info(f"Dataset {dataset_id} does not exist. Creating it.")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"  # Adjust location as needed
        dataset.default_table_expiration_ms = 3600000 * 24  # Example: 24 hours, adjust as needed
        client.create_dataset(dataset)  # Make an API request.
        log.info(f"Created dataset {dataset_id}.")

def transform_key(key):
    # Remove '@' and convert to snake_case
    key = key.replace('@', '')
    key = re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()
    return key

def filter_post(post, allowed_columns):
    return {k: v for k, v in post.items() if k in allowed_columns}

def transform_and_filter_post(post, allowed_columns):
    transformed_post = {transform_key(k): v for k, v in post.items()}
    filtered_post = filter_post(transformed_post, allowed_columns)
    return filtered_post

def transform_post(post):
    return {transform_key(k): v for k, v in post.items()}

def save_post_to_json(post, filepath):
    with open(filepath, 'w') as json_file:
        json.dump(post, json_file)

def post_bigquery(transformed_post):
    # Authenticate with Google Cloud and initialize the BigQuery client
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account.json"
    client = bigquery.Client()

    project_id = client.project
    dataset_id = 'data_devops'
    table_id = 'posts'

    create_dataset_if_not_exists(client, dataset_id, project_id)


    # Define the BigQuery table
    table_ref = client.dataset(dataset_id).table(table_id)
    table = bigquery.Table(table_ref)

    # Check if the table exists and create it if it doesn't
    try:
        client.get_table(table)
        log.info(f"Table {table_id} already exists.")
    except Exception as e:
        log.info(f"Table {table_id} does not exist. Creating it.")
        table = bigquery.Table(table_ref, schema=SCHEMA)
        table = client.create_table(table)
        log.info(f"Created table {table_id}.")

    temp_filepath = '/tmp/post.json'
    save_post_to_json(transformed_post, temp_filepath)

    # Load the JSON file into BigQuery
    with open(temp_filepath, 'rb') as json_file:
        job = client.load_table_from_file(json_file, table_ref, job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        ))

    job.result()  # Wait for the job to complete

    if job.errors is None:
        log.info(f"Inserted post with id {transformed_post['id']}")
    else:
        log.info("Encountered errors while inserting rows: {}".format(job.errors))

def post_kafka(transformed_post, kafka_host):
    # Kafka configuration
    bootstrap_servers = [kafka_host]

    # Create Producer instance
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    try:
        # Produce and send a single message
        future = producer.send(TOPIC, transformed_post)
        record_metadata = future.get(timeout=10)
        print(f"Message delivered to {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}")
    except Exception as e:
        print(f"Message delivery failed: {e}")
    finally:
        producer.close()

def main(multiple, kafka_host):
    # Load the post from the JSON file
    data_filepath = "./data/movies-stackexchange/json/posts.json"
    log.info(data_filepath)
    log.info(os.getcwd())
    with open(data_filepath, "r") as f:
        content = f.read()
    posts = json.loads(content)

    while True:
        post = random.choice(posts)

        allowed_columns = {field.name for field in SCHEMA}
        # Transform the post for insertion and save to a temporary JSON file
        transformed_post = transform_and_filter_post(post, allowed_columns)
        
        if not kafka_host:
            post_bigquery(transformed_post)
        else:
            post_kafka(transformed_post, kafka_host)

        if not args.multiple:
            break

        time.sleep(10)

# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--multiple', action='store_true', help='Send multiple messages')
    parser.add_argument('--kafka_host', type=str, required=False, default=None, help='The Kafka host address, changing BigQuery target to Kafka')
    args = parser.parse_args()

    main(
        multiple=args.multiple,
        kafka_host=args.kafka_host
    )