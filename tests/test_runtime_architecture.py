from __future__ import annotations

from _common import get_group_spec
from runtime_architecture import evaluate_runtime_architecture, normalize_runtime_architecture


def test_row1_runtime_architecture_passes() -> None:
    spec = get_group_spec('row1-memory-core')
    normalized = normalize_runtime_architecture(
        list_stdout_text='{"slots":{"memory":"memory-core","contextEngine":"legacy"},"plugins":[{"id":"memory-core","kind":"memory","enabled":true,"selected":true,"slot":"memory"}]}',
        inspect_stdout_map={'memory-core': '{"id":"memory-core","kind":"memory","enabled":true,"slot":"memory"}'},
        actual_openclaw_config={'plugins': {'slots': {'memory': 'memory-core', 'contextEngine': 'legacy'}}},
        spec=spec,
    )
    report = evaluate_runtime_architecture(spec, normalized)
    assert report['overall_passed'] is True


def test_row3_legacy_runtime_path_passes() -> None:
    spec = get_group_spec('row3-openviking-minus-core')
    normalized = normalize_runtime_architecture(
        list_stdout_text='{"slots":{"memory":"memory-openviking","contextEngine":"legacy"},"plugins":[{"id":"memory-openviking","kind":"memory","enabled":true,"selected":true,"slot":"memory"}]}',
        inspect_stdout_map={'memory-openviking': '{"id":"memory-openviking","kind":"memory","enabled":true,"slot":"memory"}'},
        actual_openclaw_config={'plugins': {'slots': {'memory': 'memory-openviking', 'contextEngine': 'legacy'}}},
        spec=spec,
    )
    report = evaluate_runtime_architecture(spec, normalized)
    assert report['checks']['row3_legacy_memory_path_proved'] is True
    assert report['overall_passed'] is True


def test_row4_coexistence_passes() -> None:
    spec = get_group_spec('row4-compat-primary')
    normalized = normalize_runtime_architecture(
        list_stdout_text='{"slots":{"memory":"memory-core","contextEngine":"openviking"},"plugins":[{"id":"memory-core","kind":"memory","enabled":true,"selected":true,"slot":"memory"},{"id":"openviking","kind":"context-engine","enabled":true,"selected":true,"slot":"contextEngine"}]}',
        inspect_stdout_map={
            'memory-core': '{"id":"memory-core","kind":"memory","enabled":true,"slot":"memory"}',
            'openviking': '{"id":"openviking","kind":"context-engine","enabled":true,"slot":"contextEngine"}',
        },
        actual_openclaw_config={'plugins': {'slots': {'memory': 'memory-core', 'contextEngine': 'openviking'}}},
        spec=spec,
    )
    report = evaluate_runtime_architecture(spec, normalized)
    assert report['checks']['row4_coexistence_proved'] is True
    assert report['overall_passed'] is True


def test_unparseable_inventory_fails_closed() -> None:
    spec = get_group_spec('row1-memory-core')
    normalized = normalize_runtime_architecture(
        list_stdout_text='not json',
        inspect_stdout_map={'memory-core': '{"id":"memory-core","kind":"memory","enabled":true,"slot":"memory"}'},
        actual_openclaw_config={'plugins': {'slots': {'memory': 'memory-core', 'contextEngine': 'legacy'}}},
        spec=spec,
    )
    report = evaluate_runtime_architecture(spec, normalized)
    assert report['overall_passed'] is False
    assert 'plugin inventory list output could not be parsed as JSON' in report['blocking_reasons']
