"""Tests that require the ``helm`` binary (skipped if not installed)."""

from __future__ import annotations


def test_helm_lint_passes(helm_lint_result):
    assert helm_lint_result.returncode == 0, helm_lint_result.stdout + helm_lint_result.stderr


def test_helm_template_renders_all_expected_kinds(helm_rendered):
    kinds = {doc["kind"] for doc in helm_rendered}
    for required in {
        "Deployment",
        "Service",
        "Ingress",
        "HorizontalPodAutoscaler",
        "PodDisruptionBudget",
        "ConfigMap",
        "ServiceAccount",
        "ServiceMonitor",
    }:
        assert required in kinds, f"missing kind {required}; got {kinds}"


def test_rendered_deployment_has_probes(helm_rendered):
    dep = next(d for d in helm_rendered if d["kind"] == "Deployment")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert "livenessProbe" in container
    assert "readinessProbe" in container


def test_rendered_deployment_has_resource_limits(helm_rendered):
    dep = next(d for d in helm_rendered if d["kind"] == "Deployment")
    res = dep["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert "limits" in res and "requests" in res


def test_rendered_deployment_drops_all_capabilities(helm_rendered):
    dep = next(d for d in helm_rendered if d["kind"] == "Deployment")
    sec = dep["spec"]["template"]["spec"]["containers"][0]["securityContext"]
    assert sec["capabilities"]["drop"] == ["ALL"]
    assert sec["allowPrivilegeEscalation"] is False
    assert sec["readOnlyRootFilesystem"] is True


def test_rendered_pod_runs_as_non_root(helm_rendered):
    dep = next(d for d in helm_rendered if d["kind"] == "Deployment")
    psc = dep["spec"]["template"]["spec"]["securityContext"]
    assert psc["runAsNonRoot"] is True
    assert psc["runAsUser"] >= 1000


def test_rendered_pod_uses_runtime_default_seccomp(helm_rendered):
    dep = next(d for d in helm_rendered if d["kind"] == "Deployment")
    psc = dep["spec"]["template"]["spec"]["securityContext"]
    assert psc["seccompProfile"]["type"] == "RuntimeDefault"


def test_rendered_hpa_targets_deployment(helm_rendered):
    hpa = next(d for d in helm_rendered if d["kind"] == "HorizontalPodAutoscaler")
    assert hpa["spec"]["scaleTargetRef"]["kind"] == "Deployment"


def test_rendered_pdb_min_available(helm_rendered):
    pdb = next(d for d in helm_rendered if d["kind"] == "PodDisruptionBudget")
    assert pdb["spec"]["minAvailable"] == 1


def test_rendered_service_selects_pods_by_label(helm_rendered):
    svc = next(d for d in helm_rendered if d["kind"] == "Service")
    assert "app.kubernetes.io/name" in svc["spec"]["selector"]
