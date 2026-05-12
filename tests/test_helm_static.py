"""Static (no-helm-binary) checks on the chart's YAML."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HELM = ROOT / "helm" / "webapp"


def test_chart_yaml_has_required_fields(chart_yaml):
    assert chart_yaml["apiVersion"] == "v2"
    assert chart_yaml["name"] == "webapp"
    assert "version" in chart_yaml and "appVersion" in chart_yaml
    assert chart_yaml["type"] == "application"


def test_values_has_safe_defaults(values_yaml):
    # never run as root in defaults
    assert values_yaml["podSecurityContext"]["runAsNonRoot"] is True
    assert values_yaml["containerSecurityContext"]["allowPrivilegeEscalation"] is False
    assert values_yaml["containerSecurityContext"]["readOnlyRootFilesystem"] is True
    assert values_yaml["containerSecurityContext"]["capabilities"]["drop"] == ["ALL"]


def test_values_defines_resource_limits(values_yaml):
    r = values_yaml["resources"]
    for k in ("cpu", "memory"):
        assert k in r["requests"]
        assert k in r["limits"]


def test_values_enables_hpa_by_default(values_yaml):
    a = values_yaml["autoscaling"]
    assert a["enabled"] is True
    assert a["minReplicas"] >= 2     # don't ship single-replica prod defaults
    assert a["maxReplicas"] >= a["minReplicas"]


def test_values_enables_pdb_by_default(values_yaml):
    pdb = values_yaml["podDisruptionBudget"]
    assert pdb["enabled"] is True
    assert pdb["minAvailable"] >= 1


def test_template_files_exist():
    for f in [
        "deployment.yaml", "service.yaml", "ingress.yaml", "hpa.yaml",
        "pdb.yaml", "configmap.yaml", "serviceaccount.yaml", "servicemonitor.yaml",
        "_helpers.tpl",
    ]:
        assert (HELM / "templates" / f).is_file(), f"missing template {f}"


def test_deployment_template_uses_rolling_update():
    txt = (HELM / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    assert "RollingUpdate" in txt
    assert "maxUnavailable: 0" in txt
