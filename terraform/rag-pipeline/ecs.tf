# ─────────────────────────────────────────────
# ECS — MCP server on Fargate
# ─────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "mcp" {
  name              = "/ecs/${var.project}/mcp-server"
  retention_in_days = 14
}

# --- Service Discovery (Cloud Map) ---

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project}.local"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "mcp_server" {
  name = "mcp-server"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config { failure_threshold = 1 }
}

# --- Task Definition ---

resource "aws_ecs_task_definition" "mcp_server" {
  family                   = "${var.project}-mcp-server"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.mcp_server_cpu
  memory                   = var.mcp_server_memory
  execution_role_arn       = aws_iam_role.ecs_task_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "mcp-server"
    image     = "${aws_ecr_repository.mcp_server.repository_url}:${var.mcp_server_image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8888
      protocol      = "tcp"
    }]
    environment = [
      { name = "MCP_TRANSPORT",              value = "sse" },
      { name = "MCP_SSE_PORT",               value = "8888" },
      { name = "RAG_OPENSEARCH_HOST",        value = aws_opensearchserverless_collection.rag_vectors.collection_endpoint },
      { name = "RAG_OPENSEARCH_REGION",      value = var.aws_region },
      { name = "RAG_OPENSEARCH_INDEX_PREFIX", value = "rag_domains" },
      { name = "BEDROCK_EMBEDDING_MODEL",    value = "amazon.titan-embed-text-v2:0" },
      { name = "BEDROCK_EMBEDDING_REGION",   value = var.aws_region },
      { name = "MCP_LLM_MODEL",             value = "anthropic.claude-3-5-sonnet-20241022-v2:0" },
      { name = "MCP_LLM_REGION",            value = var.aws_region },
      { name = "S3_RAW_BUCKET",             value = aws_s3_bucket.raw_documents.bucket },
      { name = "S3_PROCESSED_BUCKET",       value = aws_s3_bucket.processed_documents.bucket },
      { name = "PYTHONPATH",                value = "/app" },
    ]
    secrets = [
      {
        name      = "MCP_API_KEY"
        valueFrom = "${aws_secretsmanager_secret.mcp_api_key.arn}:MCP_API_KEY::"
      },
    ]
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8888/health')\" || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.mcp.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "mcp"
      }
    }
  }])
}

# --- ECS Service ---

resource "aws_ecs_service" "mcp_server" {
  name            = "mcp-server"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mcp_server.arn
  desired_count   = var.mcp_server_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.mcp_server.arn
  }
}
