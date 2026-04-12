.PHONY: fetch-upstreams setup-envs versions smoke-row1 install-ov-helper configure-ov-local smoke-row3 full-row1 full-row3 merge-row1 merge-row3 judge-row1 judge-row3 check-dataset

fetch-upstreams:
	./scripts/fetch_upstreams.sh

setup-envs:
	./scripts/setup_envs.sh

versions:
	./scripts/record_versions.sh

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

full-row1:
	./scripts/run_full_group.sh row1-memory-core

full-row3:
	./scripts/run_full_group.sh row3-openviking-minus-core

merge-row1:
	python3 scripts/merge_answers.py row1-memory-core

merge-row3:
	python3 scripts/merge_answers.py row3-openviking-minus-core

judge-row1:
	./scripts/judge_group.sh row1-memory-core

judge-row3:
	./scripts/judge_group.sh row3-openviking-minus-core
