variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "eliza-rag"
}

variable "env" {
  description = "Environment name (development, staging, production)"
  type        = string
  default     = "development"
}

# --- Networking ---

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.1.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (need at least 2 for MWAA)"
  type        = list(string)
  default     = ["10.1.1.0/24", "10.1.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (need at least 2 for MWAA)"
  type        = list(string)
  default     = ["10.1.10.0/24", "10.1.11.0/24"]
}

# --- MWAA (Managed Airflow) ---

variable "mwaa_environment_class" {
  description = "MWAA environment class (mw1.small, mw1.medium, mw1.large)"
  type        = string
  default     = "mw1.medium"
}

variable "mwaa_min_workers" {
  description = "Minimum MWAA worker count"
  type        = number
  default     = 1
}

variable "mwaa_max_workers" {
  description = "Maximum MWAA worker count"
  type        = number
  default     = 10
}

variable "mwaa_plugins_s3_path" {
  description = "S3 key for MWAA plugins.zip inside the DAG bucket (empty disables plugins)"
  type        = string
  default     = "plugins/plugins.zip"
}

variable "mwaa_webserver_access_mode" {
  description = "MWAA Airflow UI access: PUBLIC_ONLY (reachable from internet with IAM token) or PRIVATE_ONLY (only from inside VPC, e.g. via VPN)"
  type        = string
  default     = "PUBLIC_ONLY"
}

# --- SharePoint credentials (for MWAA SharePoint sync DAGs) ---

variable "sharepoint_tenant_id" {
  description = "Azure AD tenant ID for SharePoint Graph API"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sharepoint_client_id" {
  description = "Azure AD app registration client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sharepoint_client_secret" {
  description = "Azure AD app registration client secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "sharepoint_site_id" {
  description = "SharePoint site ID for Graph API"
  type        = string
  default     = ""
  sensitive   = true
}

# --- MCP Server ---

variable "mcp_api_key" {
  description = "API key for authenticating MCP server requests (leave empty to disable auth)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "mcp_server_image_tag" {
  description = "Docker image tag for the MCP server in ECR"
  type        = string
  default     = "latest"
}

variable "mcp_server_cpu" {
  description = "Fargate CPU units for MCP server (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "512"
}

variable "mcp_server_memory" {
  description = "Fargate memory (MB) for MCP server"
  type        = string
  default     = "1024"
}

variable "mcp_server_desired_count" {
  description = "Number of MCP server task replicas"
  type        = number
  default     = 1
}
