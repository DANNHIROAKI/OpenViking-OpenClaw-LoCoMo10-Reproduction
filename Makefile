.PHONY: fetch-upstreams setup-envs versions preflight status diagnose-openclaw phase-a phase-b phase-c row4-probe bundle \
	smoke-row1 install-ov-helper configure-ov-local smoke-row3 \
	patch-row2 configure-row2 smoke-row2 \
	full-row1 full-row2 full-row3 \
	merge-row1 merge-row2 merge-row3 \
	judge-row1 judge-row2 judge-row3 summary check-dataset

fetch-upstreams:
	./scripts/fetch_upstreams.sh

setup-envs:
	./scripts/setup_envs.sh

versions:
	./scripts/record_versions.sh

preflight:
	./scripts/preflight.sh

diagnose-openclaw:
	./scripts/diagnose_openclaw.sh

status:
	python3 scripts/status_matrix.py

phase-a:
	./scripts/phase_a_smoke.sh

phase-b:
	./scripts/phase_b_full_core_and_ov.sh

phase-c:
	./scripts/phase_c_row2.sh

row4-probe:
	./scripts/row4_probe.sh

bundle:
	./scripts/collect_debug_bundle.sh

check-dataset:
	python3 scripts/check_dataset.py

smoke-row1:
	./scripts/smoke_row1_memory_core.sh

install-ov-helper:
	./scripts/install_openviking_helper.sh

configure-ov-local:
	./scripts/configure_openviking_local.sh

smoke-row3:
	./scripts/smoke_row3_openviking_minus_core.sh

patch-row2:
	./scripts/patch_memory_lancedb_global.sh

configure-row2:
	./scripts/configure_memory_lancedb.sh

smoke-row2:
	./scripts/smoke_row2_lancedb.sh

full-row1:
	./scripts/run_full_group.sh row1-memory-core

full-row2:
	./scripts/run_full_group.sh row2-memory-lancedb

full-row3:
	./scripts/run_full_group.sh row3-openviking-minus-core

merge-row1:
	python3 scripts/merge_answers.py row1-memory-core --expected 1540

merge-row2:
	python3 scripts/merge_answers.py row2-memory-lancedb --expected 1540

merge-row3:
	python3 scripts/merge_answers.py row3-openviking-minus-core --expected 1540

judge-row1:
	./scripts/judge_group.sh row1-memory-core

judge-row2:
	./scripts/judge_group.sh row2-memory-lancedb

judge-row3:
	./scripts/judge_group.sh row3-openviking-minus-core

summary:
	python3 scripts/build_results_table.py
