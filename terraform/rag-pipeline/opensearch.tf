# ─────────────────────────────────────────────
# OpenSearch Serverless — RAG vector collection
# ─────────────────────────────────────────────

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.project}-rag-enc"
  type = "encryption"

  policy = jsonencode({
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${var.project}-rag-vectors"]
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.project}-rag-net"
  type = "network"

  policy = jsonencode([{
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${var.project}-rag-vectors"]
    }, {
      ResourceType = "dashboard"
      Resource     = ["collection/${var.project}-rag-vectors"]
    }]
    AllowFromPublic = false
    SourceVPCEs     = [aws_opensearchserverless_vpc_endpoint.main.id]
  }])
}

resource "aws_opensearchserverless_access_policy" "data" {
  name = "${var.project}-rag-data"
  type = "data"

  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "index"
        Resource     = ["index/${var.project}-rag-vectors/*"]
        Permission   = [
          "aoss:CreateIndex",
          "aoss:UpdateIndex",
          "aoss:DescribeIndex",
          "aoss:ReadDocument",
          "aoss:WriteDocument",
        ]
      },
      {
        ResourceType = "collection"
        Resource     = ["collection/${var.project}-rag-vectors"]
        Permission   = [
          "aoss:CreateCollectionItems",
          "aoss:DescribeCollectionItems",
          "aoss:UpdateCollectionItems",
        ]
      },
    ]
    Principal = [
      aws_iam_role.ecs_task.arn,
      aws_iam_role.mwaa_execution.arn,
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
    ]
  }])
}

resource "aws_opensearchserverless_vpc_endpoint" "main" {
  name               = "${var.project}-rag-vpce"
  vpc_id             = aws_vpc.main.id
  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.ecs.id]
}

resource "aws_opensearchserverless_collection" "rag_vectors" {
  name = "${var.project}-rag-vectors"
  type = "VECTORSEARCH"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
    aws_opensearchserverless_access_policy.data,
  ]

  tags = { Name = "${var.project}-rag-vectors" }
}
