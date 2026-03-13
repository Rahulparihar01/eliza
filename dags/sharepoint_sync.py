"""SharePoint → S3 incremental sync DAG.

Uses Microsoft Graph API delta queries to mirror a SharePoint document library
into the S3 raw landing zone. Tracks delta links in Airflow Variables for CDC.

Schedule: every 15 minutes (configurable via SHAREPOINT_SYNC_INTERVAL).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from botocore.exceptions import ClientError
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from common.s3_utils import get_raw_bucket, get_s3_client, tag_object, upload_bytes
from common.sharepoint_client import SharePointClient

logger = logging.getLogger(__name__)

SCHEDULE = os.environ.get("SHAREPOINT_SYNC_INTERVAL", "*/15 * * * *")
DAG_ID = "sharepoint_s3_sync"
DELTA_LINK_VAR_PREFIX = "sharepoint_delta_"


default_args = {
    "owner": "eliza",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id=DAG_ID,
    default_args=default_args,
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["sharepoint", "ingestion", "s3"],
    doc_md=__doc__,
)
def sharepoint_sync():

    @task()
    def list_drives() -> list[dict]:
        client = SharePointClient()
        drives = client.list_drives()
        return [{"id": d["id"], "name": d.get("name", "")} for d in drives]

    @task()
    def fetch_delta(drive: dict) -> dict:
        """Run Graph API delta query for one drive; return changed files + new delta link."""
        drive_id = drive["id"]
        var_key = f"{DELTA_LINK_VAR_PREFIX}{drive_id}"
        delta_link = Variable.get(var_key, default_var=None)

        client = SharePointClient()
        files, next_delta = client.delta(drive_id, delta_link=delta_link)

        if next_delta:
            Variable.set(var_key, next_delta)

        logger.info(f"Drive {drive_id}: {len(files)} changed files")
        return {
            "drive_id": drive_id,
            "files": [
                {
                    "id": f.id,
                    "name": f.name,
                    "path": f.path,
                    "size": f.size,
                    "content_type": f.content_type,
                    "last_modified": f.last_modified,
                    "download_url": f.download_url,
                    "etag": f.etag,
                }
                for f in files
            ],
        }

    @task()
    def download_to_s3(delta_result: dict) -> list[str]:
        """Download changed files to S3 raw bucket, preserving SharePoint folder structure."""
        drive_id = delta_result["drive_id"]
        files = delta_result["files"]
        bucket = get_raw_bucket()
        s3 = get_s3_client()
        client = SharePointClient()
        uploaded_keys: list[str] = []

        for f in files:
            if not f["download_url"]:
                continue
            try:
                s3_key = f"sharepoint/{drive_id}/{f['path']}"
                incoming_etag = f.get("etag")

                # Skip unchanged files to keep retries idempotent.
                if incoming_etag:
                    try:
                        head = s3.head_object(Bucket=bucket, Key=s3_key)
                        existing_etag = (head.get("Metadata") or {}).get("sharepoint_etag")
                        if existing_etag == incoming_etag:
                            logger.info(f"Skipping unchanged file {s3_key} (etag match)")
                            continue
                    except ClientError as exc:
                        err_code = exc.response.get("Error", {}).get("Code", "")
                        if err_code not in ("404", "NoSuchKey", "NotFound"):
                            raise

                content = client.download_file(f["download_url"])
                upload_bytes(
                    bucket,
                    s3_key,
                    content,
                    metadata={
                        "sharepoint_id": f["id"],
                        "content_type": f["content_type"],
                        "last_modified": f["last_modified"],
                        "sharepoint_etag": incoming_etag or "",
                    },
                )
                tag_object(bucket, s3_key, {
                    "source": "sharepoint",
                    "drive_id": drive_id,
                    "content_type": f["content_type"],
                })
                uploaded_keys.append(s3_key)
                logger.info(f"Uploaded {s3_key} ({f['size']} bytes)")
            except Exception:
                logger.exception(f"Failed to sync {f['name']}")

        return uploaded_keys

    @task()
    def collect_uploaded_keys(all_keys: list[list[str]]) -> dict:
        """Flatten uploaded keys into a summary dict for the document pipeline."""
        flat = [k for batch in all_keys for k in batch]
        logger.info(f"Total files synced: {len(flat)}")
        return {"bucket": get_raw_bucket(), "keys": flat, "count": len(flat)}

    @task.short_circuit()
    def has_new_files(summary: dict) -> bool:
        """Skip triggering the pipeline if no files were synced."""
        return summary.get("count", 0) > 0

    drives = list_drives()
    deltas = fetch_delta.expand(drive=drives)
    uploaded = download_to_s3.expand(delta_result=deltas)
    summary = collect_uploaded_keys(uploaded)
    gate = has_new_files(summary)

    trigger_pipeline = TriggerDagRunOperator(
        task_id="trigger_document_pipeline",
        trigger_dag_id="document_pipeline",
        conf=summary,
        wait_for_completion=False,
    )

    gate >> trigger_pipeline


sharepoint_sync()
