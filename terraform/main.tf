terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name"
  default     = "webapp"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.0.0.0/16"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource"
  default = {
    project    = "webapp"
    managed-by = "terraform"
  }
}

variable "endpoint_public_access" {
  type        = bool
  description = "Expose the Kubernetes API on a public endpoint. Off by default: the API is reachable only from inside the VPC."
  default     = false
}

variable "public_access_cidrs" {
  type        = list(string)
  description = "IPv4 CIDRs allowed to reach the public API endpoint. Required when endpoint_public_access is true."
  default     = []

  validation {
    condition     = alltrue([for c in var.public_access_cidrs : try(cidrnetmask(c) != "0.0.0.0", false)])
    error_message = "public_access_cidrs must be IPv4 CIDRs and must not include a /0 (such as 0.0.0.0/0), which opens the endpoint to every address."
  }
}

variable "cluster_log_types" {
  type        = list(string)
  description = "Control-plane log types sent to CloudWatch Logs"
  default     = ["api", "audit", "authenticator"]
}

variable "cluster_log_retention_days" {
  type        = number
  description = "Retention of the control-plane log group"
  default     = 90
}

# Minimal VPC stub — production deployments use the AWS VPC module
# (terraform-aws-modules/vpc/aws) and inject 3 public + 3 private subnets.
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = "${var.cluster_name}-vpc" })
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = "1.30"

  enabled_cluster_log_types = var.cluster_log_types

  vpc_config {
    subnet_ids              = [aws_subnet.a.id, aws_subnet.b.id]
    endpoint_private_access = true
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = var.endpoint_public_access ? var.public_access_cidrs : null
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.eks.arn
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy.cluster_kms,
    aws_cloudwatch_log_group.eks,
  ]

  lifecycle {
    precondition {
      condition     = !var.endpoint_public_access || length(var.public_access_cidrs) > 0
      error_message = "Set public_access_cidrs when endpoint_public_access is true; AWS would otherwise open the endpoint to 0.0.0.0/0."
    }
  }
}

# Envelope encryption for Kubernetes Secrets in etcd.
resource "aws_kms_key" "eks" {
  description         = "${var.cluster_name} EKS secrets encryption"
  enable_key_rotation = true
  tags                = var.tags
}

# EKS would create this group on first write with no retention; creating it
# first sets the retention and lets terraform destroy remove it.
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.cluster_log_retention_days
  tags              = var.tags
}

resource "aws_subnet" "a" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 0)
  availability_zone = "${var.region}a"
  tags              = merge(var.tags, { Name = "${var.cluster_name}-subnet-a" })
}

resource "aws_subnet" "b" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 1)
  availability_zone = "${var.region}b"
  tags              = merge(var.tags, { Name = "${var.cluster_name}-subnet-b" })
}

resource "aws_iam_role" "cluster" {
  name = "${var.cluster_name}-eks-cluster-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "eks.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role_policy" "cluster_kms" {
  name = "${var.cluster_name}-eks-secrets-kms"
  role = aws_iam_role.cluster.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["kms:Encrypt", "kms:Decrypt", "kms:ListGrants", "kms:DescribeKey"],
      Resource = aws_kms_key.eks.arn
    }]
  })
}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}
