SHELL := /bin/bash

# Path to the graph-olap monorepo (source code + Helm charts).
# Override if your monorepo is in a different location:
#   make deploy MONOREPO_ROOT=/path/to/graph-olap
MONOREPO_ROOT ?= ../../graph-olap

# Kubernetes namespace
NAMESPACE ?= graph-olap-local

# Single service to build/deploy (omit for all)
SVC ?=

.PHONY: help prereqs build build-status deploy status logs teardown

help:
	@echo "Graph OLAP - Local Deployment"
	@echo ""
	@echo "  make prereqs               Check required tools"
	@echo "  make build [SVC=name]      Build Docker images"
	@echo "  make build-status          Show which images are built and their sizes"
	@echo "  make deploy                Deploy full stack to local Kubernetes"
	@echo "  make status                Show pod/service status"
	@echo "  make logs SVC=name         Tail logs for a service"
	@echo "  make teardown              Delete namespace and all resources"
	@echo ""
	@echo "  MONOREPO_ROOT=$(MONOREPO_ROOT)"
	@echo "  NAMESPACE=$(NAMESPACE)"
	@echo ""
	@echo "Services: control-plane export-worker falkordb-wrapper ryugraph-wrapper documentation jupyter-labs"

prereqs:
	@./scripts/prereqs.sh

build: prereqs
	@MONOREPO_ROOT="$(MONOREPO_ROOT)" SVC="$(SVC)" ./scripts/build.sh

build-status:
	@printf "%-20s %-25s %-10s\n" "IMAGE" "BUILT" "SIZE"
	@printf "%-20s %-25s %-10s\n" "-----" "-----" "----"
	@for svc in control-plane export-worker falkordb-wrapper ryugraph-wrapper documentation jupyter-labs; do \
		info=$$(docker inspect $$svc:latest --format '{{.Created}} {{.Size}}' 2>/dev/null); \
		if [ -z "$$info" ]; then \
			printf "%-20s %-25s %-10s\n" "$$svc" "—" "not built"; \
		else \
			created=$$(echo $$info | awk '{print $$1}' | xargs -I{} date -j -f "%Y-%m-%dT%H:%M:%S" "{}" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "$$created"); \
			bytes=$$(echo $$info | awk '{print $$2}'); \
			mb=$$(echo "scale=0; $$bytes/1048576" | bc)MB; \
			printf "%-20s %-25s %-10s\n" "$$svc" "$$created" "$$mb"; \
		fi; \
	done

deploy: prereqs
	@MONOREPO_ROOT="$(MONOREPO_ROOT)" NAMESPACE="$(NAMESPACE)" ./scripts/deploy.sh

status:
	@echo "=== Pods ==="
	@kubectl get pods -n $(NAMESPACE) 2>/dev/null || echo "Namespace $(NAMESPACE) not found"
	@echo ""
	@echo "=== Services ==="
	@kubectl get svc -n $(NAMESPACE) 2>/dev/null || true
	@echo ""
	@echo "=== API Health ==="
	@curl -sf http://localhost:30081/health && echo " OK" || echo " not reachable (may still be starting)"

logs:
ifndef SVC
	@echo "Usage: make logs SVC=<service>"
	@echo "Services: control-plane export-worker"
else
	kubectl logs -n $(NAMESPACE) -l app=$(SVC) -f --tail=100
endif

teardown:
	@./scripts/teardown.sh $(NAMESPACE)
