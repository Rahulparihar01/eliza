# ─────────────────────────────────────────────
# API Gateway + WAF — front the standalone MCP server
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_api" "mcp" {
  name          = "${var.project}-mcp-api"
  protocol_type = "HTTP"
  tags          = { Name = "${var.project}-mcp-api" }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.mcp.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name              = "/aws/apigateway/${var.project}-mcp"
  retention_in_days = 14
}

resource "aws_apigatewayv2_vpc_link" "mcp" {
  name               = "${var.project}-mcp-vpc-link"
  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.ecs.id]
  tags               = { Name = "${var.project}-mcp-vpc-link" }
}

resource "aws_apigatewayv2_integration" "mcp" {
  api_id              = aws_apigatewayv2_api.mcp.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = aws_lb_listener.mcp.arn # VPC_LINK requires ELB listener ARN (not an HTTP URL)
  connection_type     = "VPC_LINK"
  connection_id       = aws_apigatewayv2_vpc_link.mcp.id
  payload_format_version = "1.0"
}

resource "aws_apigatewayv2_route" "mcp_proxy" {
  api_id    = aws_apigatewayv2_api.mcp.id
  route_key = "ANY /mcp/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.mcp.id}"
}

resource "aws_apigatewayv2_route" "mcp_root" {
  api_id    = aws_apigatewayv2_api.mcp.id
  route_key = "ANY /mcp"
  target    = "integrations/${aws_apigatewayv2_integration.mcp.id}"
}

# ─────────────────────────────────────────────
# WAF
# ─────────────────────────────────────────────

resource "aws_wafv2_web_acl" "mcp" {
  name  = "${var.project}-mcp-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit"
    priority = 1
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-mcp-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-common-rules"
    priority = 2
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project}-mcp-common-rules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project}-mcp-waf"
    sampled_requests_enabled   = true
  }

  tags = { Name = "${var.project}-mcp-waf" }
}

# WAFv2 AssociateWebACL does NOT support API Gateway HTTP API (v2). It only accepts
# REST API (v1) stage ARNs (arn:aws:apigateway:region::/restapis/api-id/stages/name).
# This API is HTTP API (v2), so we cannot associate the Web ACL here. To use WAF with
# this endpoint you would need either: (1) REST API instead of HTTP API, or
# (2) put CloudFront in front and attach the Web ACL to the CloudFront distribution.
# resource "aws_wafv2_web_acl_association" "mcp" { ... }
