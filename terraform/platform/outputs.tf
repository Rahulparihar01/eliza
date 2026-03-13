output "alb_dns_name" {
  description = "Point your DNS CNAME here for caylent.elizaplatform.com"
  value       = aws_lb.main.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "service_discovery_namespace" {
  value = aws_service_discovery_private_dns_namespace.main.name
}
