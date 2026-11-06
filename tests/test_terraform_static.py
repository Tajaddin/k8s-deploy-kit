"""Static checks on terraform/main.tf — no terraform binary required."""

from __future__ import annotations

import re


def _block(text: str, header: str) -> str:
    """Body of the top-level block opened by `header {` (closes at the next column-0 brace)."""
    start = text.index(header + " {")
    return text[start : text.index("\n}", start)]


def _attr(block: str, name: str) -> str:
    match = re.search(rf"^\s*{name}\s*=\s*(.+)$", block, re.MULTILINE)
    assert match, f"{name} not set"
    return match.group(1).strip()


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


def test_eks_api_endpoint_is_private_by_default(terraform_text):
    cluster = _block(terraform_text, 'resource "aws_eks_cluster" "this"')
    assert _attr(cluster, "endpoint_private_access") == "true"
    assert _attr(cluster, "endpoint_public_access") == "var.endpoint_public_access"
    assert _attr(_block(terraform_text, 'variable "endpoint_public_access"'), "default") == "false"


def test_eks_public_access_cidrs_are_explicit_and_never_open(terraform_text):
    cluster = _block(terraform_text, 'resource "aws_eks_cluster" "this"')
    assert "var.public_access_cidrs" in _attr(cluster, "public_access_cidrs")
    cidrs = _block(terraform_text, 'variable "public_access_cidrs"')
    assert _attr(cidrs, "default") == "[]"
    assert "validation {" in cidrs and '"0.0.0.0/0"' in cidrs
    # Turning the public endpoint on without an allowlist must fail at plan time.
    assert "precondition {" in cluster and "length(var.public_access_cidrs) > 0" in cluster


def test_eks_encrypts_secrets_with_a_rotating_kms_key(terraform_text):
    cluster = _block(terraform_text, 'resource "aws_eks_cluster" "this"')
    assert re.search(r'resources\s*=\s*\["secrets"\]', cluster)
    assert _attr(cluster, "key_arn") == "aws_kms_key.eks.arn"
    assert _attr(_block(terraform_text, 'resource "aws_kms_key" "eks"'), "enable_key_rotation") == "true"
    grant = _block(terraform_text, 'resource "aws_iam_role_policy" "cluster_kms"')
    assert "kms:Decrypt" in grant and "aws_kms_key.eks.arn" in grant


def test_eks_ships_control_plane_logs(terraform_text):
    cluster = _block(terraform_text, 'resource "aws_eks_cluster" "this"')
    assert _attr(cluster, "enabled_cluster_log_types") == "var.cluster_log_types"
    default = _attr(_block(terraform_text, 'variable "cluster_log_types"'), "default")
    for log_type in ("api", "audit", "authenticator"):
        assert f'"{log_type}"' in default
    group = _block(terraform_text, 'resource "aws_cloudwatch_log_group" "eks"')
    assert _attr(group, "name") == '"/aws/eks/${var.cluster_name}/cluster"'
    assert _attr(group, "retention_in_days")
    # Created before the cluster, or EKS creates the group itself with no retention.
    depends_on = re.search(r"depends_on\s*=\s*\[([^\]]*)\]", cluster)
    assert depends_on and "aws_cloudwatch_log_group.eks" in depends_on.group(1)
