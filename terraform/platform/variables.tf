variable "aws_region" {
  default = "us-east-1"
}

variable "project" {
  default = "eliza"
}

variable "env" {
  default = "development"
}

variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  default = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  default = ["10.0.10.0/24", "10.0.11.0/24"]
}

# --- Secrets (supply via terraform.tfvars or environment, NEVER hardcode) ---
variable "openai_api_key"    { sensitive = true }
variable "anthropic_api_key" { sensitive = true }
variable "groq_api_key"      { sensitive = true }
variable "pdl_api_key"       { sensitive = true }
variable "encryption_key"    { sensitive = true }
variable "admin_password"    { sensitive = true }

# --- GHCR pull credentials ---
variable "ghcr_username" { sensitive = true }
variable "ghcr_token"    { sensitive = true }

# --- Image tags ---
variable "backend_image_tag"  { default = "ftv-play-bedrock" }
variable "frontend_image_tag" { default = "ftv-play-bedrock" }
variable "logstash_image_tag" { default = "dev-latest" }

# --- Domain ---
variable "frontend_domain" { default = "caylent.elizaplatform.com" }

# --- App / Tenant ---
variable "admin_email" {
  description = "Platform admin email address (required for tenant initialization)"
  type        = string
  default     = "admin@eliza.com"
}
variable "frontend_url" {
  description = "Frontend URL for invite links. Defaults to https://<frontend_domain> if empty."
  type        = string
  default     = ""
}
