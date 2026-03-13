# ─────────────────────────────────────────────
# S3 Buckets — document staging + DAGs
# ─────────────────────────────────────────────

resource "aws_s3_bucket" "raw_documents" {
  bucket = "${var.project}-raw-documents"
  tags   = { Name = "${var.project}-raw-documents" }
}

resource "aws_s3_bucket_versioning" "raw_documents" {
  bucket = aws_s3_bucket.raw_documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_documents" {
  bucket = aws_s3_bucket.raw_documents.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_documents" {
  bucket = aws_s3_bucket.raw_documents.id
  rule {
    id     = "archive-old-versions"
    status = "Enabled"
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }
    noncurrent_version_expiration { noncurrent_days = 365 }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_documents" {
  bucket                  = aws_s3_bucket.raw_documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_s3_bucket" "processed_documents" {
  bucket = "${var.project}-processed-documents"
  tags   = { Name = "${var.project}-processed-documents" }
}

resource "aws_s3_bucket_versioning" "processed_documents" {
  bucket = aws_s3_bucket.processed_documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed_documents" {
  bucket = aws_s3_bucket.processed_documents.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "processed_documents" {
  bucket                  = aws_s3_bucket.processed_documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_s3_bucket" "airflow_dags" {
  bucket = "${var.project}-airflow-dags"
  tags   = { Name = "${var.project}-airflow-dags" }
}

resource "aws_s3_bucket_versioning" "airflow_dags" {
  bucket = aws_s3_bucket.airflow_dags.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "airflow_dags" {
  bucket = aws_s3_bucket.airflow_dags.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "airflow_dags" {
  bucket                  = aws_s3_bucket.airflow_dags.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
