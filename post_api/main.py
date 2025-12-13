from fastapi import FastAPI, HTTPException
from google.cloud import bigquery
import os

app = FastAPI()

# Specify the path to your service account JSON file
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account.json"

# Initialize the BigQuery client
client = bigquery.Client()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/posts/{post_id}")
def read_post(post_id: str):

    project_id = client.project
    dataset_id = 'data_devops'
    table_id = 'posts'

    query = f"""
        SELECT * FROM `{project_id}.{dataset_id}.{table_id}`
        WHERE id = @post_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("post_id", "STRING", post_id)
        ]
    )

    query_job = client.query(query, job_config=job_config)
    result = query_job.result()

    posts = [dict(row) for row in result]

    if not posts:
        raise HTTPException(status_code=404, detail="Post not found")

    return {"posts": posts}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)