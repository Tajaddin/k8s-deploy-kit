"""Time-to-render benchmark.

For each artifact, measures the wall-clock time to render / validate it:

* ``helm template`` for the chart
* ``kustomize build`` for the prod overlay
* python YAML parse for every committed manifest

If a binary is missing, the corresponding rows are skipped (not failed).
The bench is the closest portable approximation of "time-to-deploy
artifacts ready" — actual cluster boot time depends on the cluster.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "bench" / "results.json"


def _time(label: str, fn) -> dict:
    t0 = time.perf_counter()
    out = fn()
    dt = (time.perf_counter() - t0) * 1000.0
    return {"label": label, "ms": round(dt, 2), **out}


def _helm_template() -> dict:
    if shutil.which("helm") is None:
        return {"skipped": True}
    proc = subprocess.run(
        ["helm", "template", "test", str(ROOT / "helm" / "webapp")],
        capture_output=True, text=True, check=True,
    )
    docs = [d for d in yaml.safe_load_all(proc.stdout) if d is not None]
    return {"skipped": False, "manifests_rendered": len(docs)}


def _kustomize_build() -> dict:
    if shutil.which("kustomize") is None:
        return {"skipped": True}
    proc = subprocess.run(
        ["kustomize", "build", str(ROOT / "kustomize" / "overlays" / "prod")],
        capture_output=True, text=True, check=True,
    )
    docs = [d for d in yaml.safe_load_all(proc.stdout) if d is not None]
    return {"skipped": False, "manifests_rendered": len(docs)}


def _yaml_parse_all() -> dict:
    """Parse every committed YAML EXCEPT helm templates (those contain go-template syntax)."""
    count = 0
    bytes_read = 0
    for p in ROOT.rglob("*.yaml"):
        if ".terraform" in p.parts or "templates" in p.parts:
            continue
        txt = p.read_text(encoding="utf-8")
        bytes_read += len(txt.encode("utf-8"))
        for doc in yaml.safe_load_all(txt):
            if doc is not None:
                count += 1
    return {"docs_parsed": count, "bytes_total": bytes_read}


def _terraform_validate() -> dict:
    if shutil.which("terraform") is None:
        return {"skipped": True}
    cwd = str(ROOT / "terraform")
    subprocess.run(["terraform", "init", "-backend=false"], cwd=cwd, capture_output=True, check=True)
    subprocess.run(["terraform", "validate"], cwd=cwd, capture_output=True, check=True)
    return {"skipped": False}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    report = {
        "host": sys.platform,
        "tools_available": {
            "helm": shutil.which("helm") is not None,
            "kustomize": shutil.which("kustomize") is not None,
            "terraform": shutil.which("terraform") is not None,
        },
        "stages": [
            _time("yaml_parse_all", _yaml_parse_all),
            _time("helm_template", _helm_template),
            _time("kustomize_build", _kustomize_build),
            _time("terraform_validate", _terraform_validate),
        ],
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nwrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
