#!/usr/bin/env bash
# =============================================================================
# SYLION AEIS — Kubernetes deployment script
# =============================================================================
# Applies all manifests from the k8s/ directory in dependency order.
#
# Prerequisites:
#   - kubectl configured with a target cluster
#   - kustomize (bundled with kubectl >= 1.14)
#
# Usage:
#   ./scripts/deploy_k8s.sh              # apply with kustomize
#   ./scripts/deploy_k8s.sh --dry-run    # preview only
#   ./scripts/deploy_k8s.sh --delete     # tear down
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
DRY_RUN=false
DELETE=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --delete)  DELETE=true ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--delete]"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if ! command -v kubectl &>/dev/null; then
    echo "ERROR: kubectl not found in PATH" >&2
    exit 1
fi

if [ ! -d "$K8S_DIR" ]; then
    echo "ERROR: k8s/ directory not found at $K8S_DIR" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Apply or delete
# ---------------------------------------------------------------------------
if [ "$DELETE" = true ]; then
    echo "==> Tearing down SYLION AEIS (namespace: sylion)..."
    if [ "$DRY_RUN" = true ]; then
        kubectl delete -k "$K8S_DIR" --dry-run=client
    else
        kubectl delete -k "$K8S_DIR"
    fi
    echo "==> Teardown complete."
    exit 0
fi

echo "==> Deploying SYLION AEIS to Kubernetes..."

# Apply in dependency order for clarity (namespace first)
if [ "$DRY_RUN" = true ]; then
    echo "    (dry-run mode — no changes will be made)"
    kubectl apply -k "$K8S_DIR" --dry-run=client
else
    # 1. Namespace
    echo "    [1/5] Namespace..."
    kubectl apply -f "$K8S_DIR/namespace.yaml"

    # 2. PostgreSQL (ConfigMap + Secret + StatefulSet + Service)
    echo "    [2/5] PostgreSQL..."
    kubectl apply -f "$K8S_DIR/postgres.yaml"

    # 3. Wait for Postgres readiness
    echo "    [3/5] Waiting for PostgreSQL to become ready..."
    kubectl rollout status statefulset/postgres -n sylion --timeout=120s

    # 4. NATS JetStream
    echo "    [4/5] NATS JetStream..."
    kubectl apply -f "$K8S_DIR/nats.yaml"

    # 5. API Deployment + Service
    echo "    [5/5] API deployment..."
    kubectl apply -f "$K8S_DIR/api.yaml"

    # 6. Ingress
    echo "    [+] Ingress..."
    kubectl apply -f "$K8S_DIR/ingress.yaml"

    echo ""
    echo "==> Deployment applied. Waiting for API pods to become ready..."
    kubectl rollout status deployment/api -n sylion --timeout=180s
fi

echo ""
echo "==> Done."
echo "    Namespace : sylion"
echo "    PostgreSQL: postgres.sylion.svc.cluster.local:5432"
echo "    NATS      : nats.sylion.svc.cluster.local:4222"
echo "    API       : api.sylion.svc.cluster.local:8000"
echo ""
echo "    Check status:  kubectl get all -n sylion"
