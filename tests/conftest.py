"""Shared fixtures: render Helm templates and load Kustomize / Terraform.

If ``helm`` binary is missing we skip Helm tests instead of failing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _helm_available() -> bool:
    return shutil.which("helm") is not None


def _has_subprocess(cmd: str) -> bool:
    return shutil.which(cmd) is not None


@pytest.fixture(scope="session")
def helm_available() -> bool:
    return _helm_available()


@pytest.fixture(scope="session")
def kustomize_available() -> bool:
    return _has_subprocess("kustomize")


@pytest.fixture(scope="session")
def helm_rendered(helm_available, tmp_path_factory) -> list[dict]:
    """Returns the parsed YAML docs from `helm template` on the webapp chart.

    Skips if helm is not installed locally.
    """
    if not helm_available:
        pytest.skip("helm binary not installed; skipping helm template tests")
    out = subprocess.run(
        ["helm", "template", "test", str(ROOT / "helm" / "webapp")],
        check=True, capture_output=True, text=True,
    )
    docs = [d for d in yaml.safe_load_all(out.stdout) if d is not None]
    return docs


@pytest.fixture(scope="session")
def helm_lint_result(helm_available) -> subprocess.CompletedProcess:
    if not helm_available:
        pytest.skip("helm binary not installed; skipping helm lint")
    return subprocess.run(
        ["helm", "lint", str(ROOT / "helm" / "webapp")],
        capture_output=True, text=True,
    )


@pytest.fixture(scope="session")
def chart_yaml() -> dict:
    return yaml.safe_load((ROOT / "helm" / "webapp" / "Chart.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def values_yaml() -> dict:
    return yaml.safe_load((ROOT / "helm" / "webapp" / "values.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def base_deployment() -> dict:
    return yaml.safe_load(
        (ROOT / "kustomize" / "base" / "deployment.yaml").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="session")
def terraform_text() -> str:
    return (ROOT / "terraform" / "main.tf").read_text(encoding="utf-8")
