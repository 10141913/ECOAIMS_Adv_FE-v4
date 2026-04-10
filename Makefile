.PHONY: help check check-all lint test audit-callbacks smoke smoke-browser smoke-local smoke-canonical-crossrepo smoke-browser-local smoke-browser-canonical-crossrepo smoke-canonical smoke-browser-canonical verify-canonical-crossrepo verify-canonical-crossrepo-proof-artifact emit-canonical-crossrepo-proof-verification-summary verify-and-emit-canonical-crossrepo-proof-summary verify-and-emit-canonical-crossrepo-evidence-proof-summary show-canonical-crossrepo-proof-path show-canonical-crossrepo-proof-summary-path emit-canonical-crossrepo-evidence-bundle verify-canonical-crossrepo-evidence-bundle emit-canonical-crossrepo-evidence-bundle-verification-summary verify-and-emit-canonical-crossrepo-evidence-bundle-summary show-canonical-crossrepo-evidence-bundle-path show-canonical-crossrepo-evidence-bundle-summary-path verify-and-emit-canonical-crossrepo-evidence-chain canonical-integration-crossrepo-chain stop-frontend run-frontend-canonical show-frontend-runtime doctor-stack doctor-backend-only load-test-http patch-playbook run-dashboard run-dashboard-dev

PY := $(shell if [ -x ./ecoaims_frontend_env/bin/python ]; then echo ./ecoaims_frontend_env/bin/python; else echo python3; fi)
FE_HOST ?= 127.0.0.1
FE_PORT ?= 8050
NO_OPEN ?= 0

ECOAIMS_API_BASE_URL_CANONICAL ?= http://127.0.0.1:8008
BACKEND ?= $(if $(ECOAIMS_API_BASE_URL),$(ECOAIMS_API_BASE_URL),http://127.0.0.1:8008)

.PHONY: run-dashboard-dev
run-dashboard-dev:
	@bash ./run_dev.sh

.PHONY: run-dashboard
run-dashboard:
	@echo "DEPRECATED: gunakan 'make run-dashboard-dev' untuk dev stack (mock backend)."
	@echo "Untuk canonical (backend 8008), gunakan 'make run-frontend-canonical' atau 'make doctor-stack'."
	@bash ./run_dev.sh

help:
	@echo "Targets:"
	@echo "  make lint            - compileall (syntax guardrail)"
	@echo "  make test            - unit tests"
	@echo "  make audit-callbacks - import & build Dash app (callback registration guardrail)"
	@echo "  make smoke           - start stack (FastAPI+Dash) and run runtime smoke (MODE from env)"
	@echo "  make smoke-local     - smoke MODE=local_dev"
	@echo "  make smoke-canonical-crossrepo - strict canonical (cross-repo), no FE-local backend"
	@echo "  make smoke-browser   - run browser smoke (Playwright, optional; MODE from env)"
	@echo "  make smoke-browser-local     - browser smoke MODE=local_dev"
	@echo "  make smoke-browser-canonical-crossrepo - browser smoke strict canonical (cross-repo)"
	@echo "  make verify-canonical-crossrepo - emit audit artifact output/verification/canonical_crossrepo_proof.json"
	@echo "  make verify-canonical-crossrepo-proof-artifact - verify output/verification/canonical_crossrepo_proof.json"
	@echo "  make emit-canonical-crossrepo-proof-verification-summary - emit output/verification/canonical_crossrepo_proof.verify.json"
	@echo "  make verify-and-emit-canonical-crossrepo-proof-summary - verify + emit summary"
	@echo "  make show-canonical-crossrepo-proof-path - print FE proof path"
	@echo "  make show-canonical-crossrepo-proof-summary-path - print FE proof summary path"
	@echo "  make emit-canonical-crossrepo-evidence-bundle - emit output/verification/canonical_crossrepo_evidence_bundle.json"
	@echo "  make verify-canonical-crossrepo-evidence-bundle - verify output/verification/canonical_crossrepo_evidence_bundle.json"
	@echo "  make emit-canonical-crossrepo-evidence-bundle-verification-summary - emit output/verification/canonical_crossrepo_evidence_bundle.verify.json"
	@echo "  make verify-and-emit-canonical-crossrepo-evidence-bundle-summary - verify + emit evidence bundle summary"
	@echo "  make show-canonical-crossrepo-evidence-bundle-path - print FE evidence bundle path"
	@echo "  make show-canonical-crossrepo-evidence-bundle-summary-path - print FE evidence bundle summary path"
	@echo "  make verify-and-emit-canonical-crossrepo-evidence-chain - one-shot final FE chain entrypoint"
	@echo "  make canonical-integration-crossrepo-chain - start BE, run chain, stop BE (requires ECOAIMS_BE_REPO_PATH)"
	@echo "  make stop-frontend   - stop all processes LISTEN on FE_PORT (default 8050)"
	@echo "  make run-frontend-canonical - stop-frontend then run Dash single-process with ECOAIMS_API_BASE_URL=8008"
	@echo "  make run-dashboard-dev - start DEV stack (mock backend devtools + Dash), ports may auto-shift"
	@echo "  make show-frontend-runtime - GET /__runtime from FE_HOST:FE_PORT"
	@echo "  make doctor-backend-only - verify backend basics (health, contracts index, energy-data contract, CORS, gzip)"
	@echo "  make doctor-stack    - stop FE, verify backend, start FE canonical, verify /__runtime (operator one-liner)"
	@echo "  make load-test-http  - HTTP load test for /optimize and /api/contracts/index (ramp-up, 429 ratio, latency thresholds)"
	@echo "  make patch-playbook  - generate rekomendasi parameter patch dari report output/patch_validation"
	@echo "  make check           - lint + test + audit-callbacks + smoke"
	@echo "  make check-all       - check + smoke-browser"
	@echo "  make stack-reset     - stop FE(8060)/BE(8009), start BE 8009, warm-up, start FE 8060"
	@echo "  make stack-devtools  - alias stack-reset (devtools: BE 8009, FE 8060)"
	@echo "  make stack-canonical - start canonical stack (BE 8008, FE 8050)"
	@echo "  make mismatch-check  - check endpoint route/index/manifest/metadata (ENDPOINT_KEY='GET /path')"
	@echo "  make release-check   - recommended pre-release: check-all"
	@echo "  make release-check-canonical-crossrepo - canonical crossrepo chain (requires ECOAIMS_BE_REPO_PATH)"
	@echo "  make clean-run       - remove local runtime logs (.run/)"
	@echo "  make up              - start stack (MODE=canonical|devtools|external BACKEND=...)"
	@echo "  make down            - stop stack (MODE=canonical|devtools|external|all BACKEND=...)"
	@echo "  make restart         - restart stack"
	@echo "  make status          - show FE/BE runtime status"
	@echo "  make gen-always-on   - generate always-on service files (MODE=external|canonical|devtools)"
	@echo "  make health-contract-start  - start periodic health/contract logger (.run/health_contract.jsonl)"
	@echo "  make health-contract-stop   - stop periodic health/contract logger"
	@echo "  make health-contract-status - show logger status + tail last lines"
	@echo "  make health-contract-report - summarize contract/registry changes from jsonl log"
	@echo "  make watch-backend-start    - auto-run doctor-stack when backend contract/registry changes"
	@echo "  make watch-backend-stop     - stop watcher"
	@echo "  make watch-backend-status   - show watcher status"

lint:
	$(PY) -m compileall -q api ecoaims_backend ecoaims_frontend scripts
	@$(PY) -c "import pathlib,re,sys; pat=re.compile(r'\\bNone(?:_[A-Za-z0-9]+|[0-9]+)\\b'); roots=('api','ecoaims_backend','ecoaims_frontend','scripts'); hits=[]; \
[hits.append((str(p), i, line.strip())) for root in roots for p in pathlib.Path(root).rglob('*.py') for i,line in enumerate(p.read_text(encoding='utf-8', errors='ignore').splitlines(), start=1) if pat.search(line)]; \
(print('LINT GUARD FAIL: pola NoneX terdeteksi (mis. None_v2 / None2).') or [print(f'{fp}:{ln}: {txt}') for fp,ln,txt in hits[:80]] or sys.exit(1)) if hits else sys.exit(0)"

test:
	ECOAIMS_HTTP_TRACE_HEADERS=false $(PY) -m unittest discover -s ecoaims_frontend/tests -p 'test*.py' -v

audit-callbacks:
	$(PY) scripts/audit_callbacks.py

smoke:
	$(PY) scripts/smoke_stack.py

smoke-local:
	ECOAIMS_REQUIRE_CANONICAL_POLICY=false $(PY) scripts/smoke_stack.py

smoke-canonical-crossrepo:
	ECOAIMS_REQUIRE_CANONICAL_POLICY=true $(PY) scripts/smoke_canonical_crossrepo.py

smoke-browser:
	$(PY) scripts/smoke_browser_stack.py

smoke-browser-local:
	ECOAIMS_REQUIRE_CANONICAL_POLICY=false $(PY) scripts/smoke_browser_stack.py

smoke-browser-canonical-crossrepo:
	ECOAIMS_REQUIRE_CANONICAL_POLICY=true $(PY) scripts/smoke_browser_canonical_crossrepo.py

# Backward-compatible aliases (canonical means crossrepo)
smoke-canonical: smoke-canonical-crossrepo
smoke-browser-canonical: smoke-browser-canonical-crossrepo

verify-canonical-crossrepo:
	ECOAIMS_REQUIRE_CANONICAL_POLICY=true $(PY) scripts/verify_canonical_crossrepo.py

verify-canonical-crossrepo-proof-artifact:
	$(PY) scripts/verify_canonical_crossrepo_proof_artifact.py --path output/verification/canonical_crossrepo_proof.json

emit-canonical-crossrepo-proof-verification-summary:
	$(PY) scripts/verify_canonical_crossrepo_proof_artifact.py --path output/verification/canonical_crossrepo_proof.json --emit-summary --json | cat

verify-and-emit-canonical-crossrepo-proof-summary: verify-canonical-crossrepo-proof-artifact emit-canonical-crossrepo-proof-verification-summary

verify-and-emit-canonical-crossrepo-evidence-proof-summary: verify-canonical-crossrepo emit-canonical-crossrepo-proof-verification-summary

emit-canonical-crossrepo-evidence-bundle:
	$(PY) scripts/emit_canonical_crossrepo_evidence_bundle.py

verify-canonical-crossrepo-evidence-bundle:
	$(PY) scripts/verify_canonical_crossrepo_evidence_bundle.py --path output/verification/canonical_crossrepo_evidence_bundle.json

emit-canonical-crossrepo-evidence-bundle-verification-summary:
	$(PY) scripts/verify_canonical_crossrepo_evidence_bundle.py --path output/verification/canonical_crossrepo_evidence_bundle.json --emit-summary --json | cat

verify-and-emit-canonical-crossrepo-evidence-bundle-summary: verify-canonical-crossrepo-evidence-bundle emit-canonical-crossrepo-evidence-bundle-verification-summary

show-canonical-crossrepo-evidence-bundle-path:
	@echo output/verification/canonical_crossrepo_evidence_bundle.json

show-canonical-crossrepo-evidence-bundle-summary-path:
	@echo output/verification/canonical_crossrepo_evidence_bundle.verify.json

verify-and-emit-canonical-crossrepo-evidence-chain: verify-canonical-crossrepo emit-canonical-crossrepo-proof-verification-summary emit-canonical-crossrepo-evidence-bundle verify-and-emit-canonical-crossrepo-evidence-bundle-summary

canonical-integration-crossrepo-chain:
	$(PY) scripts/run_canonical_integration_chain.py

stop-frontend:
	ECOAIMS_DASH_PORT=$(FE_PORT) $(PY) scripts/stop_frontend_port.py --port $(FE_PORT)

run-frontend-canonical: stop-frontend
	ECOAIMS_DASH_HOST=$(FE_HOST) ECOAIMS_DASH_PORT=$(FE_PORT) ECOAIMS_API_BASE_URL=$(ECOAIMS_API_BASE_URL_CANONICAL) $(PY) scripts/run_frontend_canonical.py

show-frontend-runtime:
	$(PY) -c "import json, urllib.request; url='http://$(FE_HOST):$(FE_PORT)/__runtime'; print(json.dumps(json.loads(urllib.request.urlopen(url, timeout=3).read().decode('utf-8')), indent=2, sort_keys=True))"

doctor-backend-only:
	$(PY) scripts/verify_backend_api_basics.py --base-url "$(BACKEND)" --origin "http://$(FE_HOST):$(FE_PORT)"

doctor-stack:
	$(PY) scripts/doctor_stack.py --backend "$(BACKEND)" --host "$(FE_HOST)" --port "$(FE_PORT)"

load-test-http:
	ECOAIMS_LOAD_BASE_URL="$(BACKEND)" $(PY) scripts/load_test_http.py

patch-playbook:
	$(PY) scripts/patch_playbook.py --only-failed --n 3

show-canonical-crossrepo-proof-path:
	@echo output/verification/canonical_crossrepo_proof.json

show-canonical-crossrepo-proof-summary-path:
	@echo output/verification/canonical_crossrepo_proof.verify.json

check: lint test audit-callbacks smoke

check-all: check smoke-browser

release-check: check-all

release-check-canonical-crossrepo:
	$(PY) scripts/run_canonical_integration_chain.py

clean-run:
	@rm -rf .run

MODE ?= canonical
BACKEND ?=
WITH_SMOKE ?= 0

up:
	@CMD="$(MODE)"; \
	if [ "$$CMD" = "external" ]; then \
		if [ -z "$(BACKEND)" ]; then echo "BACKEND wajib untuk MODE=external (contoh BACKEND=http://127.0.0.1:8009)"; exit 2; fi; \
		./bin/ecoaims up --mode external --backend-url "$(BACKEND)"; \
	else \
		./bin/ecoaims up --mode "$$CMD"; \
	fi

down:
	@CMD="$(MODE)"; \
	if [ "$$CMD" = "external" ]; then \
		./bin/ecoaims down --mode external --backend-url "$(BACKEND)"; \
	else \
		./bin/ecoaims down --mode "$$CMD"; \
	fi

restart:
	@CMD="$(MODE)"; \
	if [ "$$CMD" = "external" ]; then \
		if [ -z "$(BACKEND)" ]; then echo "BACKEND wajib untuk MODE=external"; exit 2; fi; \
		./bin/ecoaims restart --mode external --backend-url "$(BACKEND)"; \
	else \
		./bin/ecoaims restart --mode "$$CMD"; \
	fi

status:
	@CMD="$(MODE)"; \
	if [ "$$CMD" = "external" ]; then \
		./bin/ecoaims status --mode external --backend-url "$(BACKEND)"; \
	else \
		./bin/ecoaims status --mode "$$CMD"; \
	fi

gen-always-on:
	@ECOAIMS_FE_REPO="$(PWD)" $(PY) scripts/gen_always_on_services.py --mode "$(MODE)"

.PHONY: health-contract-start
health-contract-start:
	@mkdir -p .run
	@if [ -f .run/health_contract.pid ] && kill -0 "$$(cat .run/health_contract.pid 2>/dev/null)" 2>/dev/null; then echo "health-contract already running (pid=$$(cat .run/health_contract.pid))"; exit 0; fi
	@rm -f .run/health_contract.pid 2>/dev/null || true
	@ECOAIMS_HEALTH_CONTRACT_OUT=".run/health_contract.jsonl" ECOAIMS_HEALTH_CONTRACT_STATE=".run/health_contract_last.json" $(PY) scripts/health_contract_dashboard.py >/dev/null 2>&1 & echo $$! > .run/health_contract.pid
	@sleep 0.2
	@echo "health-contract started pid=$$(cat .run/health_contract.pid) out=.run/health_contract.jsonl"

.PHONY: health-contract-stop
health-contract-stop:
	@if [ -f .run/health_contract.pid ]; then pid="$$(cat .run/health_contract.pid 2>/dev/null || true)"; if [ -n "$$pid" ] && kill -0 "$$pid" 2>/dev/null; then kill "$$pid" 2>/dev/null || true; fi; rm -f .run/health_contract.pid 2>/dev/null || true; echo "health-contract stopped"; else echo "health-contract not running"; fi

.PHONY: health-contract-status
health-contract-status:
	@pid=""; if [ -f .run/health_contract.pid ]; then pid="$$(cat .run/health_contract.pid 2>/dev/null || true)"; fi; \
	if [ -n "$$pid" ] && kill -0 "$$pid" 2>/dev/null; then echo "health-contract running pid=$$pid"; else echo "health-contract not running"; fi; \
	if [ -f .run/health_contract.jsonl ]; then echo "tail .run/health_contract.jsonl"; tail -n 5 .run/health_contract.jsonl; fi

.PHONY: health-contract-report
health-contract-report:
	@$(PY) scripts/health_contract_report.py --path ".run/health_contract.jsonl"

.PHONY: watch-backend-start
watch-backend-start:
	@mkdir -p .run
	@if [ -f .run/watch_backend.pid ] && kill -0 "$$(cat .run/watch_backend.pid 2>/dev/null)" 2>/dev/null; then echo "watch-backend already running (pid=$$(cat .run/watch_backend.pid))"; exit 0; fi
	@rm -f .run/watch_backend.pid 2>/dev/null || true
	@EXTRA=""; if [ "$(WITH_SMOKE)" = "1" ]; then EXTRA="--with-smoke"; fi; \
	BACKEND="$(BACKEND)" $(PY) scripts/backend_change_watchdog.py --backend "$(BACKEND)" $$EXTRA >/dev/null 2>&1 & echo $$! > .run/watch_backend.pid
	@sleep 0.2
	@echo "watch-backend started pid=$$(cat .run/watch_backend.pid) backend=$(BACKEND) with_smoke=$(WITH_SMOKE)"

.PHONY: watch-backend-stop
watch-backend-stop:
	@if [ -f .run/watch_backend.pid ]; then pid="$$(cat .run/watch_backend.pid 2>/dev/null || true)"; if [ -n "$$pid" ] && kill -0 "$$pid" 2>/dev/null; then kill "$$pid" 2>/dev/null || true; fi; rm -f .run/watch_backend.pid 2>/dev/null || true; echo "watch-backend stopped"; else echo "watch-backend not running"; fi

.PHONY: watch-backend-status
watch-backend-status:
	@pid=""; if [ -f .run/watch_backend.pid ]; then pid="$$(cat .run/watch_backend.pid 2>/dev/null || true)"; fi; \
	if [ -n "$$pid" ] && kill -0 "$$pid" 2>/dev/null; then echo "watch-backend running pid=$$pid backend=$(BACKEND)"; else echo "watch-backend not running"; fi

.PHONY: stack-reset
stack-reset:
	@echo "==> Stopping FE on 8060 (if any)"
	FE_PORT=8060 $(PY) scripts/stop_frontend_port.py --port 8060
	@echo "==> Stopping BE on 8009 (if any)"
	- lsof -nP -iTCP:8009 -sTCP:LISTEN -t | xargs kill -9 >/dev/null 2>&1 || true
	@sleep 0.5
	@echo "==> Starting BE (devtools canonical) on 8009"
	ECOAIMS_STACK_MODE=devtools ECOAIMS_SCHEMA_VERSION=startup_info_v1 ECOAIMS_CONTRACT_VERSION=2026-03-13 $(PY) -m uvicorn ecoaims_backend.devtools.canonical_fastapi_app:app --host 127.0.0.1 --port 8009 >/dev/null 2>&1 &
	@sleep 1.0
	@echo "==> Warm-up backend readiness & registry"
	ECOAIMS_STACK_MODE=devtools ECOAIMS_API_BASE_URL=http://127.0.0.1:8009 $(PY) scripts/wait_for_backend_ready.py || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8009/api/startup-info', timeout=3).read(); print('warm: /api/startup-info OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8009/api/contracts/index', timeout=3).read(); print('warm: /api/contracts/index OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8009/api/contracts/ecoaims-contract-v1', timeout=3).read(); print('warm: /api/contracts/ecoaims-contract-v1 OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8009/diag/doctor', timeout=3).read(); print('warm: /diag/doctor OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8009/diag/monitoring', timeout=3).read(); print('warm: /diag/monitoring OK')" || true
	@echo "==> Starting FE on 8060 (canonical pointing to 8009)"
	@ECOAIMS_STACK_MODE=devtools ECOAIMS_DASH_HOST=127.0.0.1 ECOAIMS_DASH_PORT=8060 ECOAIMS_API_BASE_URL=http://127.0.0.1:8009 $(PY) scripts/run_frontend_canonical.py >/dev/null 2>&1 &
	@sleep 1.0
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8060/__runtime', timeout=3).read(); print('warm: FE __runtime OK')" || true
	@if [ "$(NO_OPEN)" = "1" ]; then echo "==> NO_OPEN=1 (skip browser open)"; else TS=$$(date +%s); URL="http://127.0.0.1:8060/?v=$$TS"; echo "==> Open: $$URL"; open "$$URL" >/dev/null 2>&1 || true; fi

.PHONY: stack-devtools
stack-devtools: stack-reset

.PHONY: stack-canonical
stack-canonical:
	@echo "==> Stopping FE on 8050 (if any)"
	FE_PORT=8050 $(PY) scripts/stop_frontend_port.py --port 8050
	@echo "==> Stopping BE on 8008 (if any)"
	- lsof -nP -iTCP:8008 -sTCP:LISTEN -t | xargs kill -9 >/dev/null 2>&1 || true
	@mkdir -p .run
	@sleep 0.5
	@echo "==> Starting BE (canonical) on 8008"
	ECOAIMS_STACK_MODE=canonical ECOAIMS_SCHEMA_VERSION=startup_info_v1 ECOAIMS_CONTRACT_VERSION=2026-03-13 $(PY) -m uvicorn ecoaims_backend.devtools.canonical_fastapi_app:app --host 127.0.0.1 --port 8008 >.run/backend_canonical.log 2>&1 &
	@sleep 1.0
	@echo "==> Warm-up backend readiness & registry"
	ECOAIMS_STACK_MODE=canonical ECOAIMS_API_BASE_URL=http://127.0.0.1:8008 $(PY) scripts/wait_for_backend_ready.py || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8008/api/startup-info', timeout=3).read(); print('warm: /api/startup-info OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8008/api/contracts/index', timeout=3).read(); print('warm: /api/contracts/index OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8008/api/contracts/ecoaims-contract-v1', timeout=3).read(); print('warm: /api/contracts/ecoaims-contract-v1 OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8008/diag/doctor', timeout=3).read(); print('warm: /diag/doctor OK')" || true
	@$(PY) -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8008/diag/monitoring', timeout=3).read(); print('warm: /diag/monitoring OK')" || true
	@echo "==> Starting FE on 8050 (canonical pointing to 8008)"
	@ECOAIMS_STACK_MODE=canonical ECOAIMS_DASH_HOST=127.0.0.1 ECOAIMS_DASH_PORT=8050 ECOAIMS_API_BASE_URL=http://127.0.0.1:8008 ECOAIMS_REQUIRE_CANONICAL_POLICY=true $(PY) scripts/run_frontend_canonical.py >.run/frontend_canonical.log 2>&1 &
	@sh -c 'for i in $$(seq 1 50); do if curl -sf "http://127.0.0.1:8050/__runtime" >/dev/null 2>&1; then echo "warm: FE __runtime OK"; exit 0; fi; sleep 0.5; done; echo "warm: FE __runtime FAIL (see .run/frontend_canonical.log)"; exit 1'
	@if [ "$(NO_OPEN)" = "1" ]; then echo "==> NO_OPEN=1 (skip browser open)"; else TS=$$(date +%s); URL="http://127.0.0.1:8050/?v=$$TS"; echo "==> Open: $$URL"; open "$$URL" >/dev/null 2>&1 || true; fi

.PHONY: mismatch-check
mismatch-check:
	@$(PY) scripts/check_endpoint_contract.py --base-url "$${ECOAIMS_API_BASE_URL:-http://127.0.0.1:8009}" --endpoint-key "$${ENDPOINT_KEY}"
