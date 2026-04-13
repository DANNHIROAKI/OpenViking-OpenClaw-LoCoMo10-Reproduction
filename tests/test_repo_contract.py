from __future__ import annotations

from pathlib import Path

from repo_contract import (
    CI_WORKFLOW,
    ENV_EXAMPLE,
    GITIGNORE_PATH,
    disallowed_env_example_vars,
    gitignore_missing_required_patterns,
    missing_env_example_vars,
    official_targets_uses_mutable_refs,
    required_env_example_vars,
    tracked_junk_files,
    workflow_missing_required_commands,
)


def test_env_example_exists() -> None:
    assert ENV_EXAMPLE.exists()


def test_ci_workflow_exists() -> None:
    assert CI_WORKFLOW.exists()


def test_gitignore_exists() -> None:
    assert GITIGNORE_PATH.exists()


def test_env_example_covers_required_template_and_script_vars() -> None:
    missing = missing_env_example_vars()
    assert missing == [], f'.env.example missing keys: {missing}; required={sorted(required_env_example_vars())}'


def test_env_example_omits_runtime_generated_vars() -> None:
    assert disallowed_env_example_vars() == []


def test_ci_workflow_contains_required_static_commands() -> None:
    assert workflow_missing_required_commands() == []


def test_gitignore_contains_required_patterns() -> None:
    assert gitignore_missing_required_patterns() == []


def test_official_targets_use_immutable_refs() -> None:
    assert official_targets_uses_mutable_refs() == []


def test_repo_has_no_tracked_junk_files() -> None:
    assert tracked_junk_files() == []