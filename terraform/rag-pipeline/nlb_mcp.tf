# ─────────────────────────────────────────────
# NLB in front of MCP server — required for API Gateway VPC Link
# VPC Link only accepts an ELB listener ARN (or Cloud Map ARN), not an HTTP URL.
# ─────────────────────────────────────────────

resource "aws_lb" "mcp" {
  name               = "${var.project}-mcp-nlb"
  load_balancer_type = "network"
  internal           = true
  subnets            = aws_subnet.private[*].id

  tags = { Name = "${var.project}-mcp-nlb" }
}

resource "aws_lb_target_group" "mcp" {
  name        = "${var.project}-mcp-tg"
  port        = 8888
  protocol    = "TCP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    protocol            = "TCP"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 30
  }

  tags = { Name = "${var.project}-mcp-tg" }
}

resource "aws_lb_listener" "mcp" {
  load_balancer_arn = aws_lb.mcp.arn
  port              = "80"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp.arn
  }
}
