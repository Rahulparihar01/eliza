# ─────────────────────────────────────────────
# Secrets Manager — SharePoint credentials for MWAA DAGs
# ─────────────────────────────────────────────

resource "aws_secretsmanager_secret" "sharepoint_creds" {
  name                    = "${var.project}/${var.env}/sharepoint-credentials"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "sharepoint_creds" {
  secret_id = aws_secretsmanager_secret.sharepoint_creds.id
  secret_string = jsonencode({
    SHAREPOINT_TENANT_ID     = var.sharepoint_tenant_id
    SHAREPOINT_CLIENT_ID     = var.sharepoint_client_id
    SHAREPOINT_CLIENT_SECRET = var.sharepoint_client_secret
    SHAREPOINT_SITE_ID       = var.sharepoint_site_id
  })
}

# ─────────────────────────────────────────────
# Secrets Manager — MCP server API key
# ─────────────────────────────────────────────

resource "aws_secretsmanager_secret" "mcp_api_key" {
  name                    = "${var.project}/${var.env}/mcp-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "mcp_api_key" {
  secret_id = aws_secretsmanager_secret.mcp_api_key.id
  secret_string = jsonencode({
    MCP_API_KEY = var.mcp_api_key
  })
}
