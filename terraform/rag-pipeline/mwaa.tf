# ─────────────────────────────────────────────
# MWAA (Managed Workflows for Apache Airflow)
# ─────────────────────────────────────────────

resource "aws_s3_object" "airflow_requirements" {
  bucket = aws_s3_bucket.airflow_dags.id
  key    = "requirements/requirements.txt"
  source = "${path.module}/files/requirements-airflow.txt"
  etag   = filemd5("${path.module}/files/requirements-airflow.txt")
}

# Startup script sets S3 bucket names and OpenSearch endpoint for RAG DAGs.
locals {
  startup_script_vars = {
    raw_bucket             = aws_s3_bucket.raw_documents.bucket
    processed_bucket       = aws_s3_bucket.processed_documents.bucket
    opensearch_host        = aws_opensearchserverless_collection.rag_vectors.collection_endpoint
    aws_region             = var.aws_region
    opensearch_index_prefix = "rag_domains"
  }
  startup_script_content = templatefile("${path.module}/files/startup.sh.tpl", local.startup_script_vars)
}

resource "aws_s3_object" "startup_script" {
  bucket  = aws_s3_bucket.airflow_dags.id
  key     = "startup.sh"
  content = local.startup_script_content
  etag    = md5(local.startup_script_content)
}

resource "aws_mwaa_environment" "main" {
  name               = "${var.project}-mwaa"
  airflow_version    = "2.10.3" # MWAA supported versions: 2.7.2, 2.8.1, 2.9.2, 2.10.1, 2.10.3, 2.11.0, 3.0.6 (2.10.4 not supported)
  execution_role_arn = aws_iam_role.mwaa_execution.arn

  source_bucket_arn = aws_s3_bucket.airflow_dags.arn
  dag_s3_path       = "dags/"
  requirements_s3_path           = aws_s3_object.airflow_requirements.key
  requirements_s3_object_version = aws_s3_object.airflow_requirements.version_id
  plugins_s3_path = var.mwaa_plugins_s3_path != "" ? var.mwaa_plugins_s3_path : null

  startup_script_s3_path           = aws_s3_object.startup_script.key
  startup_script_s3_object_version = aws_s3_object.startup_script.version_id

  environment_class = var.mwaa_environment_class

  max_workers = var.mwaa_max_workers
  min_workers = var.mwaa_min_workers

  network_configuration {
    security_group_ids = [aws_security_group.mwaa.id]
    subnet_ids         = aws_subnet.private[*].id
  }

  webserver_access_mode = var.mwaa_webserver_access_mode

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }
    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }
    task_logs {
      enabled   = true
      log_level = "INFO"
    }
    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }
    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }

  airflow_configuration_options = {
    "core.load_examples" = "false"
    "secrets.backend"    = "airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend"
    "secrets.backend_kwargs" = jsonencode({
      connections_prefix = "${var.project}/${var.env}/airflow/connections"
      variables_prefix   = "${var.project}/${var.env}/airflow/variables"
      full_url_mode      = false
    })
  }

  tags = { Name = "${var.project}-mwaa" }
}
