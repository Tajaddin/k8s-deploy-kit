# Plans against a mocked AWS provider: no credentials, no resources created.
mock_provider "aws" {}

run "defaults_are_private_encrypted_and_logged" {
  command = plan

  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].endpoint_private_access && !aws_eks_cluster.this.vpc_config[0].endpoint_public_access
    error_message = "The API endpoint must be private-only by default."
  }

  assert {
    condition     = one(aws_eks_cluster.this.encryption_config).resources == toset(["secrets"])
    error_message = "Kubernetes Secrets must be envelope-encrypted with KMS."
  }

  assert {
    condition     = toset(aws_eks_cluster.this.enabled_cluster_log_types) == toset(["api", "audit", "authenticator"])
    error_message = "api, audit and authenticator control-plane logs must be on by default."
  }
}

run "public_endpoint_with_allowlist" {
  command = plan

  variables {
    endpoint_public_access = true
    public_access_cidrs    = ["203.0.113.0/24"]
  }

  assert {
    condition     = toset(aws_eks_cluster.this.vpc_config[0].public_access_cidrs) == toset(["203.0.113.0/24"])
    error_message = "The allowlist must reach the cluster's vpc_config."
  }
}

run "public_endpoint_without_allowlist_is_rejected" {
  command = plan

  variables {
    endpoint_public_access = true
  }

  expect_failures = [aws_eks_cluster.this]
}

run "open_cidr_is_rejected" {
  command = plan

  variables {
    endpoint_public_access = true
    public_access_cidrs    = ["0.0.0.0/0"]
  }

  expect_failures = [var.public_access_cidrs]
}

run "malformed_cidr_is_rejected" {
  command = plan

  variables {
    endpoint_public_access = true
    public_access_cidrs    = ["203.0.113.0"]
  }

  expect_failures = [var.public_access_cidrs]
}
