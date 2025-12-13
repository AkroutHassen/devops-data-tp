from google.cloud import bigquery
import os

# Authentification
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account.json"

# Configuration
DATASET_ID = "data_devops"
TABLE_ID = "posts"

client = bigquery.Client()

# 1. Création du Dataset
dataset_ref = client.dataset(DATASET_ID)
try:
    client.get_dataset(dataset_ref)
    print(f"Dataset {DATASET_ID} existe déjà.")
except Exception:
    print(f"Création du dataset {DATASET_ID}...")
    client.create_dataset(dataset_ref)

# 2. Définition du Schéma (Aligné avec post_pusher)
schema = [
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
    bigquery.SchemaField('content_license', 'STRING', mode='NULLABLE'),
    bigquery.SchemaField('parent_id', 'STRING', mode='NULLABLE')
]

# 3. Création de la table
table_ref = dataset_ref.table(TABLE_ID)
table = bigquery.Table(table_ref, schema=schema)

try:
    client.create_table(table)
    print(f"Table {TABLE_ID} créée avec succès !")
except Exception as e:
    print(f"Info : {e}")
    
   