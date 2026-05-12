"""Static checks on Kustomize base + overlays (no binary required)."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
KUSTOMIZE = ROOT / "kustomize"


def test_kustomize_base_kustomization_lists_resources():
    k = yaml.safe_load((KUSTOMIZE / "base" / "kustomization.yaml").read_text(encoding="utf-8"))
    assert "deployment.yaml" in k["resources"]
    assert "service.yaml" in k["resources"]


def test_base_deployment_has_securityContext(base_deployment):
    sc = base_deployment["spec"]["template"]["spec"]["securityContext"]
    assert sc["runAsNonRoot"] is True


def test_base_deployment_has_resource_limits(base_deployment):
    res = base_deployment["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert "limits" in res and "requests" in res


def test_dev_overlay_targets_base():
    k = yaml.safe_load((KUSTOMIZE / "overlays" / "dev" / "kustomization.yaml").read_text(encoding="utf-8"))
    assert "../../base" in k["resources"]
    assert k["namespace"] == "webapp-dev"


def test_prod_overlay_scales_up_replicas():
    k = yaml.safe_load((KUSTOMIZE / "overlays" / "prod" / "kustomization.yaml").read_text(encoding="utf-8"))
    patches = k["patches"]
    rendered = "\n".join(p.get("patch", "") for p in patches)
    assert "replicas" in rendered
    assert "value: 4" in rendered


def test_overlays_use_distinct_namespaces():
    dev = yaml.safe_load((KUSTOMIZE / "overlays" / "dev" / "kustomization.yaml").read_text(encoding="utf-8"))
    prod = yaml.safe_load((KUSTOMIZE / "overlays" / "prod" / "kustomization.yaml").read_text(encoding="utf-8"))
    assert dev["namespace"] != prod["namespace"]
