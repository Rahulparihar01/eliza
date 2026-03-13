resource "aws_secretsmanager_secret" "api_keys" {
  name = "${var.project}/${var.env}/api-keys-v3"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    OPENAI_API_KEY         = var.openai_api_key
    ANTHROPIC_API_KEY      = var.anthropic_api_key
    GROQ_API_KEY           = var.groq_api_key
    PDL_API_KEY            = var.pdl_api_key
    ENCRYPTION_KEY         = var.encryption_key
    ADMIN_PASSWORD         = var.admin_password
    DATABASE_URL           = "postgresql://user:password@postgres.${var.project}.local:5432/ai_enablement"
    INSURANCE_DEMO_DB_URL  = "postgresql://user:password@postgres.${var.project}.local:5432/insurance_demo_db"
    NEO4J_PASSWORD         = "password"
    REDIS_URL              = "redis://redis.${var.project}.local:6379"
    CELERY_BROKER_URL      = "redis://redis.${var.project}.local:6379/0"
    CELERY_RESULT_BACKEND  = "redis://redis.${var.project}.local:6379/1"
    FLOWER_BASIC_AUTH      = "admin:${var.admin_password}"
  })
}

# GHCR pull credentials for ECS
resource "aws_secretsmanager_secret" "ghcr_creds" {
  name = "${var.project}/${var.env}/ghcr-credentials-v3"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "ghcr_creds" {
  secret_id     = aws_secretsmanager_secret.ghcr_creds.id
  secret_string = jsonencode({
    username = var.ghcr_username
    password = var.ghcr_token
  })
}