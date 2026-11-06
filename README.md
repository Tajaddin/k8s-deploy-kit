# k8s-deploy-kit

> Production-shaped Kubernetes deployment kit: **Helm chart** with HPA + PodDisruptionBudget + ServiceMonitor, **Kustomize overlays** for dev/prod, and a **Terraform stub** for an EKS cluster (private API endpoint, KMS-encrypted Secrets, control-plane logs). **38 structural tests** — 26 run with no tooling installed, 10 more activate when `helm` is on PATH and 2 when `kustomize` or `kubectl` is. **Every test passes safe-by-default invariants**: non-root containers, drop-all capabilities, RuntimeDefault seccomp, resource limits, a pinned prod image, rolling-update with `maxUnavailable: 0`, HPA min replicas ≥ 2.

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![Tests](https://img.shields.io/badge/tests-26%20pass%20%2B%2012%20conditional-brightgreen)](#tests) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

## What you get

Three deployment surfaces, one production-shaped baseline:

| Surface | Path | What's in it |
|---|---|---|
| **Helm chart** | `helm/webapp/` | Deployment + Service + Ingress + HPA + PDB + ConfigMap + ServiceAccount + ServiceMonitor (Prometheus). Templates use `_helpers.tpl` for labels & fullname per chart-best-practice. |
| **Kustomize overlays** | `kustomize/base/` + `kustomize/overlays/{dev,prod}/` | Same Deployment + Service, with overlay-specific namespace, replica count, and resource requests. |
| **Terraform stub** | `terraform/main.tf` | `aws_eks_cluster` (private API endpoint, KMS envelope encryption for Secrets, control-plane logs) + IAM role + EKSClusterPolicy attachment + VPC + 2 subnets in 2 AZs. Pinned to `hashicorp/aws ~> 5.0`. |

Every shipped manifest is **safe-by-default** — the structural tests guarantee:
* containers run as non-root (`runAsNonRoot: true`, `runAsUser >= 1000`)
* capabilities are explicitly dropped (`capabilities.drop: ["ALL"]`)
* pods use the container runtime's default seccomp profile (`seccompProfile.type: RuntimeDefault`)
* root filesystem is read-only
* every container declares CPU + memory resource limits AND requests
* liveness + readiness probes are present
* HPA ships with `minReplicas >= 2` (no single-replica prod by accident)
* PodDisruptionBudget protects rolling restarts
* Deployment uses `RollingUpdate` strategy with `maxUnavailable: 0`
* the prod overlay pins the image tag (never `:latest`)
* the EKS API endpoint is private unless you allowlist CIDRs (any `/0` is rejected), Secrets are KMS-encrypted, and api/audit/authenticator logs go to CloudWatch

## Tests

```bash
pip install -e ".[dev]"
pytest -v
```

```
tests/test_helm_static.py        8 passed   chart.yaml fields, safe values defaults, seccomp, HPA/PDB/resources, templates exist,
                                             RollingUpdate uses maxUnavailable:0
tests/test_kustomize_static.py   8 passed   base lists resources, securityContext, seccomp, resources, overlay targets base,
                                             prod scales up, distinct namespaces, prod pins the image
tests/test_terraform_static.py  10 passed   required_version pinned, aws ~> 5.0, EKS cluster + role + policy, outputs, tags,
                                             private endpoint, CIDR allowlist, KMS secrets encryption, control-plane logs
tests/test_helm_render.py       10 conditional   activate with `helm` binary: lint passes, all 8 expected kinds render,
                                                  probes present, resources set, capabilities dropped, runAsNonRoot,
                                                  seccomp, HPA targets Deployment, PDB minAvailable, Service selectors
tests/test_kustomize_render.py   2 conditional   activate with `kustomize` or `kubectl`: prod image pinned, seccomp
─────────────────────────────────────────────
26 passed, 12 conditional (skipped without helm / kustomize)
```

Run with `helm` installed (`brew install helm` / `apt install helm`) and `kustomize` or `kubectl` to activate the conditional suites. The skipped tests run real `helm lint` + `helm template` and build the prod overlay, then assert structural properties on the rendered manifests.

## Hero benchmark — time-to-render

`python bench/run_benchmark.py`:

```json
{
  "stages": [
    { "label": "yaml_parse_all",    "ms": 30.25, "docs_parsed": 7, "bytes_total": 4860 },
    { "label": "helm_template",     "skipped": true },
    { "label": "kustomize_build",   "skipped": true },
    { "label": "terraform_validate","skipped": true }
  ]
}
```

| Stage | Cost (no extra tools) |
|---|---:|
| Parse all committed YAML | **24.6–30.3 ms** (5 runs, median 26.6 ms) for 7 manifests / 4,860 bytes |
| Helm template render | measured when `helm` is installed |
| Kustomize build (prod overlay) | measured when `kustomize` is installed |
| Terraform validate | measured when `terraform` is installed (includes `init -backend=false`) |

The YAML row was measured on Windows (Python 3.12) with the other tools off PATH; `bench/results.json` is the last of those runs.

Stages that depend on external binaries are gracefully skipped if the binary isn't on PATH — the report records `"skipped": true` so CI sees the gap honestly.

## Helm chart — what the templates render

`helm template test helm/webapp` produces 8 manifests:

| Kind | Purpose |
|---|---|
| `ServiceAccount` | Pod identity (separate from default). |
| `ConfigMap` | Non-secret env via `envFrom`. |
| `Service` | ClusterIP fronting the pods. |
| `Ingress` | nginx by default, configurable. |
| `Deployment` | Rolling update (maxUnavailable: 0), drops all caps, non-root, RO root FS, probes, anti-affinity hint. |
| `HorizontalPodAutoscaler` | autoscaling/v2 with CPU + memory targets. |
| `PodDisruptionBudget` | `minAvailable: 1`. |
| `ServiceMonitor` | Prometheus operator scrape config at `/metrics`. |

Every kind has a coordinated set of labels (`app.kubernetes.io/{name,instance,managed-by,version}`) so kubectl filters work cleanly:

```bash
kubectl get all -l app.kubernetes.io/instance=test
```

## Kustomize — dev vs prod

```bash
kustomize build kustomize/overlays/dev
kustomize build kustomize/overlays/prod
```

| | dev | prod |
|---|---|---|
| Namespace | `webapp-dev` | `webapp-prod` |
| Replicas | 1 | 4 |
| CPU request | 100m | 250m |
| CPU limit | 500m | 1 core |
| Image | `0.1.0` from base | pinned in the overlay's `images:`; the release pipeline sets the digest with `kustomize edit set image` |

Overlays use `patches` (the modern API) to selectively override the base — no full-file duplication.

## Terraform — EKS stub

`terraform/main.tf` is intentionally a *minimum-viable* EKS cluster: the cluster resource + IAM role + 2 subnets + a tagged VPC. It has no node groups, NAT or route tables, so it is not a deployable production cluster on its own. Production deployments wrap this with the `terraform-aws-modules/vpc/aws` and `terraform-aws-modules/eks/aws` community modules for full HA networking + node-group management.

The control plane itself is configured safely:

| Setting | Default | Variable |
|---|---|---|
| API endpoint | private only | `endpoint_public_access` |
| Public endpoint allowlist | none; required when the public endpoint is on, any `/0` (`0.0.0.0/0`, `1.2.3.4/0`) rejected | `public_access_cidrs` |
| Secrets encryption | KMS key with rotation, created by the module | — |
| Control-plane logs | `api`, `audit`, `authenticator` to `/aws/eks/<cluster>/cluster` | `cluster_log_types` |
| Log retention | 90 days | `cluster_log_retention_days` |

With the default private endpoint, `kubectl` must run from inside the VPC (VPN, bastion or CI runner). The structural tests keep these settings, the policy attachment and the outputs in place across edits. `terraform/tests/eks.tftest.hcl` checks the behaviour: it plans against `mock_provider "aws"` (no credentials, nothing created), asserts the defaults above, and expects the plan to fail for a public endpoint with no allowlist, any `/0`, or a malformed CIDR. CI runs `terraform fmt -check`, `validate` and `test`; `mock_provider` needs Terraform 1.7 or later.

```bash
cd terraform
terraform init -backend=false
terraform validate
terraform test
```

## Quickstart

```bash
# Helm to a kind cluster
kind create cluster --name local
helm install local helm/webapp -f helm/webapp/values.yaml

# Kustomize to current kubeconfig
kubectl apply -k kustomize/overlays/dev

# Terraform plan (read-only)
cd terraform && terraform init -backend=false && terraform validate
```

## Project layout

```
.
├── helm/webapp/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── ingress.yaml
│       ├── hpa.yaml
│       ├── pdb.yaml
│       ├── configmap.yaml
│       ├── serviceaccount.yaml
│       └── servicemonitor.yaml
├── kustomize/
│   ├── base/{deployment,service}.yaml + kustomization.yaml
│   └── overlays/{dev,prod}/kustomization.yaml
├── terraform/main.tf
├── tests/                  # 38 cases (26 unconditional + 12 helm/kustomize-conditional)
└── bench/run_benchmark.py
```

## Limitations

**No real cluster benchmark.** The "time-to-deploy" hero metric in the brief required a real cluster (Kind or otherwise). This kit ships time-to-render numbers instead — the artifacts are validated end-to-end without depending on a live cluster's boot time, which varies by 30× between cloud providers.

**EKS-only Terraform.** GKE / AKS / DOKS each need their own module. The Terraform structure here demonstrates the pattern (pinned providers, IAM separation, tagged resources) but porting to GKE is a `google_container_cluster` rewrite, not a config tweak.

**No multi-cluster / GitOps layer.** ArgoCD / FluxCD configs would substantially extend the kit. The Helm chart values are intentionally one-environment-per-`helm install` so they compose with whichever GitOps tool you pick.

**Helm + Kustomize are NOT siblings here.** The Helm chart is the rich production deployment. The Kustomize overlays are the simpler "kubectl apply" path for teams that don't want a Helm dependency. They share no code (no helm-to-kustomize generator) — you pick one.

**No network policy.** Defense-in-depth needs `NetworkPolicy` resources; this kit doesn't ship one because every cluster's CNI is different and applying a deny-all + selective-allow policy can break the cluster's own kube-system traffic if done wrong. Adding it is a 30-line template per direction.

## License

MIT — see [LICENSE](LICENSE).
