"""Tests that build the prod overlay (skipped without kustomize or kubectl)."""

from __future__ import annotations


def _deployment(docs: list[dict]) -> dict:
    return next(d for d in docs if d["kind"] == "Deployment")


def test_rendered_prod_image_is_pinned(prod_overlay_rendered):
    image = _deployment(prod_overlay_rendered)["spec"]["template"]["spec"]["containers"][0]["image"]
    if "@sha256:" in image:
        return
    repo_and_tag = image.rsplit("/", 1)[-1]
    assert ":" in repo_and_tag, f"prod image has no tag: {image}"
    assert not repo_and_tag.endswith(":latest"), f"prod image floats on latest: {image}"


def test_rendered_prod_pod_uses_runtime_default_seccomp(prod_overlay_rendered):
    psc = _deployment(prod_overlay_rendered)["spec"]["template"]["spec"]["securityContext"]
    assert psc["seccompProfile"]["type"] == "RuntimeDefault"
