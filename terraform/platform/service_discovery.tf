# AWS Cloud Map for internal DNS (replaces Northflank's internal hostnames)
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project}.local"
  vpc  = aws_vpc.main.id
}

locals {
  discovery_services = [
    "postgres", "redis", "neo4j", "elasticsearch",
    "logstash", "kibana", "app", "flower"
  ]
}

resource "aws_service_discovery_service" "services" {
  for_each = toset(local.discovery_services)
  name     = each.key
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"
    dns_records { 
      ttl = 10
      type = "A" 
      }
  }
  health_check_custom_config { failure_threshold = 1 }
}