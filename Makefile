GROUP ?= row1-memory-core
RUN_ID ?= manual-run
STAGE ?= micro
MODE ?= full
RUNTIME_ENV_FILE := runtime_configs/$(RUN_ID)/$(GROUP)/exports.env

.PHONY: benchmark source-manifest freeze-versions preflight preflight-group preflight-group-online materialize probe micro extended full judge finalize verify summary claim-readiness repeatability audit-sample audit-summary tail-appendix

benchmark:
	python3 scripts/build_benchmark.py

source-manifest:
	python3 scripts/generate_source_manifest.py

freeze-versions:
	python3 scripts/freeze_versions.py

preflight:
	python3 scripts/preflight.py

preflight-group:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) python3 scripts/preflight.py --group $(GROUP) --run-id $(RUN_ID)

preflight-group-online:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) python3 scripts/preflight.py --group $(GROUP) --run-id $(RUN_ID) --online

materialize:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID)

probe:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) ./scripts/run_probe.sh $(GROUP) $(RUN_ID)

micro:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) ./scripts/run_smoke.sh $(GROUP) $(RUN_ID) micro

extended:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) ./scripts/run_smoke.sh $(GROUP) $(RUN_ID) extended

full:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) ./scripts/run_full_group.sh $(GROUP) $(RUN_ID)

judge:
	python3 scripts/materialize_configs.py $(GROUP) $(RUN_ID) >/dev/null
	REPRO_RUNTIME_ENV_FILE=$(RUNTIME_ENV_FILE) ./scripts/run_judge.sh $(GROUP) $(RUN_ID) $(MODE) $(if $(filter smoke,$(MODE)),$(STAGE),)

finalize:
	python3 scripts/finalize_group.py $(GROUP) $(RUN_ID) --mode $(MODE) $(if $(filter smoke,$(MODE)),--stage $(STAGE),)

verify:
	python3 scripts/verify_group_outputs.py $(GROUP) $(RUN_ID) --mode $(MODE) $(if $(filter smoke,$(MODE)),--stage $(STAGE),)

summary:
	python3 scripts/build_results_summary.py

claim-readiness:
	python3 scripts/build_claim_readiness.py

repeatability:
	python3 scripts/build_repeatability_report.py

audit-sample:
	python3 scripts/generate_manual_audit_sample.py $(GROUP) --run-id $(RUN_ID)

audit-summary:
	python3 scripts/summarize_manual_audit.py

tail-appendix:
	python3 scripts/run_tail_sensitivity_appendix.py $(GROUP) $(RUN_ID)
