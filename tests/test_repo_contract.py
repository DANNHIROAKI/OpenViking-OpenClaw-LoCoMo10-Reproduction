from __future__ import annotations

from pathlib import Path

from repo_contract import (
    CI_WORKFLOW,
    ENV_EXAMPLE,
    disallowed_env_example_vars,
    missing_env_example_vars,
    required_env_example_vars,
    workflow_missing_required_commands,
)



def test_env_example_exists() -> None:
    assert ENV_EXAMPLE.exists()



def test_ci_workflow_exists() -> None:
    assert CI_WORKFLOW.exists()



def test_env_example_covers_required_template_and_script_vars() -> None:
    missing = missing_env_example_vars()
    assert missing == [], f'.env.example missing keys: {missing}; required={sorted(required_env_example_vars())}'



def test_env_example_omits_runtime_generated_vars() -> None:
    assert disallowed_env_example_vars() == []



def test_ci_workflow_contains_required_static_commands() -> None:
    assert workflow_missing_required_commands() == []
