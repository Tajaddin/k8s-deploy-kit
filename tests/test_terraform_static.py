"""Static checks on terraform/main.tf — no terraform binary required."""

from __future__ import annotations


def test_terraform_pins_required_version(terraform_text):
    assert "required_version" in terraform_text


def test_terraform_pins_aws_provider_version(terraform_text):
    assert "hashicorp/aws" in terraform_text
    assert "~> 5.0" in terraform_text


def test_terraform_has_eks_cluster_resource(terraform_text):
    assert 'resource "aws_eks_cluster"' in terraform_text
    assert 'role_arn = aws_iam_role.cluster.arn' in terraform_text


def test_terraform_attaches_eks_policy(terraform_text):
    assert "AmazonEKSClusterPolicy" in terraform_text


def test_terraform_outputs_cluster_name_and_endpoint(terraform_text):
    assert 'output "cluster_name"' in terraform_text
    assert 'output "cluster_endpoint"' in terraform_text


def test_terraform_tags_resources(terraform_text):
    # Tags should be applied to at least the VPC and cluster
    assert "tags                 = merge(var.tags" in terraform_text or "tags = var.tags" in terraform_text
