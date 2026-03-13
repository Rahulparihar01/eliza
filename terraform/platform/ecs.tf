resource "aws_ecs_cluster" "main" {
  name = "${var.project}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project}"
  retention_in_days = 7
}

locals {
  ghcr_registry_auth = aws_secretsmanager_secret.ghcr_creds.arn
  exec_role          = aws_iam_role.ecs_task_exec.arn
  task_role          = aws_iam_role.ecs_task.arn
  log_config = { logDriver = "awslogs", options = {
    awslogs-group         = aws_cloudwatch_log_group.ecs.name
    awslogs-region        = var.aws_region
    awslogs-stream-prefix = "ecs"
  }}
}

# ─────────────────────────────────────────────
# POSTGRES
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "postgres" {
  family                   = "${var.project}-postgres"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = local.exec_role
  task_role_arn            = local.task_role

  volume {
    name = "postgres-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.volumes["postgres-data"].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.volumes["postgres-data"].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "postgres"
    image     = "postgres:15"
    essential = true
    portMappings = [{
      containerPort = 5432
      protocol      = "tcp"
    }]
    environment = [
      { name = "POSTGRES_DB",       value = "ai_enablement" },
      { name = "POSTGRES_USER",     value = "user" },
      { name = "POSTGRES_PASSWORD", value = "password" },
      { name = "PGDATA",            value = "/var/lib/postgresql/data/pgdata" }
    ]
    mountPoints = [{
      sourceVolume  = "postgres-data"
      containerPath = "/var/lib/postgresql/data"
    }]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "postgres" {
  name            = "postgres"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.postgres.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.services["postgres"].arn
  }
}

# ─────────────────────────────────────────────
# REDIS
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "redis" {
  family                   = "${var.project}-redis"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "512"
  memory = "1024"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  volume {
    name = "redis-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.volumes["redis-data"].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.volumes["redis-data"].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "redis"
    image     = "redis:7-alpine"
    essential = true
    portMappings = [{
      containerPort = 6379
      protocol      = "tcp"
    }]
    mountPoints = [{
      sourceVolume  = "redis-data"
      containerPath = "/data"
    }]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "redis" {
  name            = "redis"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.redis.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["redis"].arn
  }
}

# ─────────────────────────────────────────────
# NEO4J
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "neo4j" {
  family                   = "${var.project}-neo4j"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "1024"
  memory = "2048"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  volume {
    name = "neo4j-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.volumes["neo4j-data"].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.volumes["neo4j-data"].id
        iam             = "ENABLED"
      }
    }
  }
  volume {
    name = "neo4j-logs"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.volumes["neo4j-logs"].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.volumes["neo4j-logs"].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "neo4j"
    image     = "neo4j:5.13"
    essential = true
    portMappings = [
      {
        containerPort = 7687
        protocol      = "tcp"
      },
      {
        containerPort = 7474
        protocol      = "tcp"
      }
    ]
    environment = [
      { name = "NEO4J_AUTH",                                             value = "neo4j/password" },
      { name = "NEO4J_PLUGINS",                                          value = "[\"apoc\"]" },
      { name = "NEO4J_dbms_security_procedures_unrestricted",            value = "apoc.*" },
      { name = "NEO4J_dbms_memory_heap_initial__size",                   value = "512M" },
      { name = "NEO4J_dbms_memory_heap_max__size",                       value = "1G" }
    ]
    mountPoints = [
      {
        sourceVolume  = "neo4j-data"
        containerPath = "/data"
      },
      {
        sourceVolume  = "neo4j-logs"
        containerPath = "/logs"
      }
    ]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "neo4j" {
  name            = "neo4j"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.neo4j.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["neo4j"].arn
  }
}

# ─────────────────────────────────────────────
# ELASTICSEARCH
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "elasticsearch" {
  family                   = "${var.project}-elasticsearch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "1024"
  memory = "2048"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  volume {
    name = "elasticsearch-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.volumes["elasticsearch-data"].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.volumes["elasticsearch-data"].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "elasticsearch"
    image     = "docker.elastic.co/elasticsearch/elasticsearch:8.11.0"
    essential = true
    portMappings = [
      {
        containerPort = 9200
        protocol      = "tcp"
      },
      {
        containerPort = 9300
        protocol      = "tcp"
      }
    ]
    environment = [
      { name = "discovery.type",                       value = "single-node" },
      { name = "xpack.security.enabled",               value = "false" },
      { name = "xpack.security.enrollment.enabled",    value = "false" },
      { name = "ES_JAVA_OPTS",                          value = "-Xms1g -Xmx1g" }
    ]
    mountPoints = [{
      sourceVolume  = "elasticsearch-data"
      containerPath = "/usr/share/elasticsearch/data"
    }]
    logConfiguration = local.log_config
    ulimits = [{
      name      = "nofile"
      softLimit = 65536
      hardLimit = 65536
    }]
  }])
}

resource "aws_ecs_service" "elasticsearch" {
  name            = "elasticsearch"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.elasticsearch.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["elasticsearch"].arn
  }
}

# ─────────────────────────────────────────────
# LOGSTASH
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "logstash" {
  family                   = "${var.project}-logstash"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "512"
  memory = "1024"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "logstash"
    image     = "ghcr.io/eliza-hq/elizaplatform-logstash:${var.logstash_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    portMappings = [
      {
        containerPort = 5000
        protocol      = "tcp"
      },
      {
        containerPort = 9600
        protocol      = "tcp"
      }
    ]
    environment = [
      { name = "LS_JAVA_OPTS",                              value = "-Xms512m -Xmx512m" },
      { name = "xpack.monitoring.enabled",                  value = "true" },
      { name = "xpack.monitoring.elasticsearch.hosts",      value = "http://elasticsearch.${var.project}.local:9200" }
    ]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "logstash" {
  name            = "logstash"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.logstash.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["logstash"].arn
  }
  depends_on = [aws_ecs_service.elasticsearch]
}

# ─────────────────────────────────────────────
# KIBANA
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "kibana" {
  family                   = "${var.project}-kibana"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "1024"
  memory = "2048"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "kibana"
    image     = "docker.elastic.co/kibana/kibana:8.11.0"
    essential = true
    portMappings = [{
      containerPort = 5601
      protocol      = "tcp"
    }]
    environment = [
      { name = "ELASTICSEARCH_HOSTS",                  value = "http://elasticsearch.${var.project}.local:9200" },
      { name = "XPACK_SECURITY_ENABLED",               value = "false" },
      { name = "XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY", value = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0" },
      { name = "SERVER_SSL_ENABLED",                   value = "false" }
    ]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "kibana" {
  name            = "kibana"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.kibana.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["kibana"].arn
  }
  depends_on = [aws_ecs_service.elasticsearch]
}

# ─────────────────────────────────────────────
# APP (Backend)  — secrets injected from Secrets Manager
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "1024"
  memory = "2048"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "app"
    image     = "ghcr.io/eliza-hq/elizaplatform-backend:${var.backend_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    portMappings = [{
      containerPort = 5001
      protocol      = "tcp"
    }]
    secrets = [
      { name = "OPENAI_API_KEY",        valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:OPENAI_API_KEY::" },
      { name = "ANTHROPIC_API_KEY",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:ANTHROPIC_API_KEY::" },
      { name = "GROQ_API_KEY",          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:GROQ_API_KEY::" },
      { name = "PDL_API_KEY",           valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:PDL_API_KEY::" },
      { name = "ENCRYPTION_KEY",        valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:ENCRYPTION_KEY::" },
      { name = "DATABASE_URL",          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:DATABASE_URL::" },
      { name = "REDIS_URL",             valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:REDIS_URL::" },
      { name = "CELERY_BROKER_URL",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_BROKER_URL::" },
      { name = "CELERY_RESULT_BACKEND", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_RESULT_BACKEND::" },
      { name = "ADMIN_PASSWORD",        valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:ADMIN_PASSWORD::" },
      { name = "INSURANCE_DEMO_DB_URL",  valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:INSURANCE_DEMO_DB_URL::" }
    ]
    environment = [
      { name = "CUSTOMER_ID",             value = "eliza" },
      { name = "CUSTOMER_NAME",           value = "Eliza Platform" },
      { name = "RUN_MIGRATIONS",          value = "true" },
      { name = "INIT_TENANT",             value = "true" },
      { name = "ADMIN_EMAIL",             value = var.admin_email },
      { name = "FRONTEND_URL",            value = var.frontend_url != "" ? var.frontend_url : "https://${var.frontend_domain}" },
      { name = "ENVIRONMENT",             value = var.env },
      { name = "NEO4J_URI",               value = "bolt://neo4j.${var.project}.local:7687" },
      { name = "NEO4J_USER",              value = "neo4j" },
      { name = "NEO4J_PASSWORD",          value = "password" },
      { name = "ELASTICSEARCH_HOSTS",     value = "http://elasticsearch.${var.project}.local:9200" },
      { name = "LOGSTASH_HOST",           value = "logstash.${var.project}.local" },
      { name = "LOGSTASH_PORT",           value = "5000" },
      { name = "LOGSTASH_ENABLED",        value = "true" },
      { name = "LOG_LEVEL",               value = "INFO" },
      { name = "LOG_TO_FILE",             value = "true" },
      { name = "LOG_JSON_FORMAT",         value = "true" },
      { name = "PYTHONPATH",              value = "/app" },
      { name = "ALLOWED_HOSTS",           value = "caylent.elizaplatform.com,eliza-alb-704906039.us-east-1.elb.amazonaws.com,app.eliza.local,app,localhost,127.0.0.1,10.0.1.71,10.0.2.120" },
      { name = "ALLOWED_ORIGINS",         value = "https://${var.frontend_domain},http://localhost:3000" },
      { name = "DEFAULT_LLM_MODEL",       value = "gpt-4o-mini" },
      { name = "ELASTICSEARCH_SYNC_ENABLED", value = "true" },
      { name = "NEO4J_SYNC_ENABLED",      value = "true" },
      { name = "CREWAI_LOG_LEVEL",        value = "INFO" },
      { name = "CREWAI_SAVE_LOGS",        value = "true" }
    ]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "app" {
  name            = "app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 5001
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["app"].arn
  }
  depends_on = [aws_ecs_service.postgres, aws_ecs_service.redis]
}

# ─────────────────────────────────────────────
# CELERY WORKER
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "celery_worker" {
  family                   = "${var.project}-celery-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "1024"
  memory = "2048"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "celery-worker"
    image     = "ghcr.io/eliza-hq/elizaplatform-backend:${var.backend_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    command   = ["python", "-m", "celery", "-A", "src.celery_app", "worker",
                 "--loglevel=info", "--concurrency=4", "--max-tasks-per-child=100"]
    secrets = [
      { name = "OPENAI_API_KEY",        valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:OPENAI_API_KEY::" },
      { name = "ANTHROPIC_API_KEY",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:ANTHROPIC_API_KEY::" },
      { name = "DATABASE_URL",          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:DATABASE_URL::" },
      { name = "CELERY_BROKER_URL",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_BROKER_URL::" },
      { name = "CELERY_RESULT_BACKEND", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_RESULT_BACKEND::" }
    ]
    environment = [
      { name = "PYTHONPATH", value = "/app" },
      { name = "NEO4J_URI",  value = "bolt://neo4j.${var.project}.local:7687" },
      { name = "NEO4J_USER", value = "neo4j" }
    ]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "celery_worker" {
  name            = "celery-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery_worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  depends_on = [aws_ecs_service.redis, aws_ecs_service.postgres]
}

# ─────────────────────────────────────────────
# CELERY BEAT
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "celery_beat" {
  family                   = "${var.project}-celery-beat"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "512"
  memory = "1024"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "celery-beat"
    image     = "ghcr.io/eliza-hq/elizaplatform-backend:${var.backend_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    command   = ["python", "-m", "celery", "-A", "src.celery_app", "beat", "--loglevel=info"]
    secrets = [
      { name = "CELERY_BROKER_URL",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_BROKER_URL::" },
      { name = "CELERY_RESULT_BACKEND", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_RESULT_BACKEND::" },
      { name = "DATABASE_URL",          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:DATABASE_URL::" }
    ]
    environment = [{ name = "PYTHONPATH", value = "/app" }]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "celery_beat" {
  name            = "celery-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery_beat.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  depends_on = [aws_ecs_service.redis]
}

# ─────────────────────────────────────────────
# CELERY INGESTION WORKER
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "celery_ingestion" {
  family                   = "${var.project}-celery-ingestion"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "512"
  memory = "1024"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "celery-ingestion-worker"
    image     = "ghcr.io/eliza-hq/elizaplatform-backend:${var.backend_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    command   = ["celery", "-A", "src.celery_app", "worker",
                 "--loglevel=info", "--concurrency=2", "--max-tasks-per-child=10",
                 "-Q", "ingestion", "--prefetch-multiplier=1"]
    secrets = [
      { name = "CELERY_BROKER_URL",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_BROKER_URL::" },
      { name = "CELERY_RESULT_BACKEND", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_RESULT_BACKEND::" },
      { name = "DATABASE_URL",          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:DATABASE_URL::" }
    ]
    environment = [{ name = "PYTHONPATH", value = "/app" }]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "celery_ingestion" {
  name            = "celery-ingestion-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery_ingestion.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  depends_on = [aws_ecs_service.redis]
}

# ─────────────────────────────────────────────
# FLOWER
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "flower" {
  family                   = "${var.project}-flower"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "512"
  memory = "1024"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "flower"
    image     = "ghcr.io/eliza-hq/elizaplatform-backend:${var.backend_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    command   = ["celery", "-A", "src.celery_app", "flower", "--port=5555"]
    portMappings = [{
      containerPort = 5555
      protocol      = "tcp"
    }]
    secrets = [
      { name = "CELERY_BROKER_URL",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_BROKER_URL::" },
      { name = "CELERY_RESULT_BACKEND", valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CELERY_RESULT_BACKEND::" },
      { name = "FLOWER_BASIC_AUTH",     valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:FLOWER_BASIC_AUTH::" }
    ]
    environment = [{ name = "PYTHONPATH", value = "/app" }]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "flower" {
  name            = "flower"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.flower.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.services["flower"].arn
  }
  depends_on = [aws_ecs_service.redis]
}

# ─────────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────────
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "512"
  memory = "1024"
  execution_role_arn = local.exec_role
  task_role_arn      = local.task_role

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "ghcr.io/eliza-hq/elizaplatform-frontend:${var.frontend_image_tag}"
    essential = true
    repositoryCredentials = { credentialsParameter = local.ghcr_registry_auth }
    portMappings = [{
      containerPort = 80
      protocol      = "tcp"
    }]
    logConfiguration = local.log_config
  }])
}

resource "aws_ecs_service" "frontend" {
  name            = "frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }
  depends_on = [aws_lb_listener.http]
}