from __future__ import annotations

from typing import Any

from _common import parse_json_text


PLUGIN_ID_KEYS = ('id', 'name', 'plugin_id', 'pluginId')
KIND_KEYS = ('kind', 'type', 'pluginKind', 'pluginType')
ENABLED_KEYS = ('enabled', 'isEnabled')
SELECTED_KEYS = ('selected', 'active', 'isSelected', 'isActive', 'current')
SLOT_KEYS = ('slot', 'slotName')


def _normalize_kind(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace('_', '-').replace(' ', '-')
    if text in {'contextengine', 'context-engine'}:
        return 'context-engine'
    if text in {'memory'}:
        return 'memory'
    if text in {'legacy'}:
        return 'legacy'
    return text or None


def _normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {'true', '1', 'yes', 'enabled', 'active'}:
        return True
    if lowered in {'false', '0', 'no', 'disabled', 'inactive'}:
        return False
    return None


def _plugin_id_from_obj(obj: dict[str, Any]) -> str | None:
    for key in PLUGIN_ID_KEYS:
        value = obj.get(key)
        if value not in (None, ''):
            return str(value)
    return None


def _collect_slots(node: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(node, dict):
        slots = node.get('slots')
        if isinstance(slots, dict):
            for key in ['memory', 'contextEngine', 'context-engine']:
                value = slots.get(key)
                if value not in (None, ''):
                    norm_key = 'contextEngine' if key in {'contextEngine', 'context-engine'} else key
                    out[norm_key] = str(value)
        plugins = node.get('plugins')
        if isinstance(plugins, dict):
            out.update(_collect_slots(plugins))
        for value in node.values():
            if isinstance(value, (dict, list)):
                child = _collect_slots(value)
                out.update({k: v for k, v in child.items() if k not in out})
    elif isinstance(node, list):
        for item in node:
            child = _collect_slots(item)
            out.update({k: v for k, v in child.items() if k not in out})
    return out


def _extract_plugins_from_list_json(data: Any) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    plugins: dict[str, dict[str, Any]] = {}
    selected_slots: dict[str, str] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            # direct slots block
            slots = node.get('slots')
            if isinstance(slots, dict):
                for key in ['memory', 'contextEngine', 'context-engine']:
                    value = slots.get(key)
                    if value not in (None, ''):
                        norm_key = 'contextEngine' if key in {'contextEngine', 'context-engine'} else key
                        selected_slots[norm_key] = str(value)

            plugin_id = _plugin_id_from_obj(node)
            kind = None
            for key in KIND_KEYS:
                if node.get(key) not in (None, ''):
                    kind = _normalize_kind(node.get(key))
                    break
            enabled = None
            for key in ENABLED_KEYS:
                if key in node:
                    enabled = _normalize_bool(node.get(key))
                    break
            selected = None
            for key in SELECTED_KEYS:
                if key in node:
                    selected = _normalize_bool(node.get(key))
                    break
            slot = None
            for key in SLOT_KEYS:
                if node.get(key) not in (None, ''):
                    slot = str(node.get(key))
                    break

            if plugin_id:
                current = plugins.setdefault(plugin_id, {'present': True})
                current['present'] = True
                if kind is not None:
                    current['kind'] = kind
                if enabled is not None:
                    current['enabled'] = enabled
                if slot is not None:
                    current['slot'] = slot
                if selected is not None:
                    current['selected'] = selected
                    if selected is True and slot in {'memory', 'contextEngine', 'context-engine'}:
                        norm_key = 'contextEngine' if slot in {'contextEngine', 'context-engine'} else slot
                        selected_slots[norm_key] = plugin_id

            for value in node.values():
                if isinstance(value, (dict, list)):
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(data)
    return plugins, selected_slots


def _extract_plugin_from_inspect_json(plugin_id: str, data: Any) -> dict[str, Any]:
    info: dict[str, Any] = {'present': True}
    candidate = data if isinstance(data, dict) else {}
    # descend common wrappers
    for key in ['plugin', 'data', 'result']:
        value = candidate.get(key)
        if isinstance(value, dict):
            maybe_id = _plugin_id_from_obj(value)
            if maybe_id == plugin_id or maybe_id is None:
                candidate = value
                break
    kind = None
    for key in KIND_KEYS:
        if candidate.get(key) not in (None, ''):
            kind = _normalize_kind(candidate.get(key))
            break
    enabled = None
    for key in ENABLED_KEYS:
        if key in candidate:
            enabled = _normalize_bool(candidate.get(key))
            break
    slot = None
    for key in SLOT_KEYS:
        if candidate.get(key) not in (None, ''):
            slot = str(candidate.get(key))
            break
    if kind is not None:
        info['kind'] = kind
    if enabled is not None:
        info['enabled'] = enabled
    if slot is not None:
        info['slot'] = slot
    return info


def normalize_runtime_architecture(
    *,
    list_stdout_text: str,
    inspect_stdout_map: dict[str, str],
    actual_openclaw_config: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    list_json = parse_json_text(list_stdout_text)
    list_parsed = list_json is not None
    plugins: dict[str, dict[str, Any]] = {}
    selected_slots: dict[str, str] = {}
    if list_parsed:
        extracted_plugins, extracted_slots = _extract_plugins_from_list_json(list_json)
        plugins.update(extracted_plugins)
        selected_slots.update(extracted_slots)

    inspect_json_parsed: dict[str, bool] = {}
    inspect_parsed_json: dict[str, Any] = {}
    for plugin_id, stdout in inspect_stdout_map.items():
        data = parse_json_text(stdout)
        inspect_json_parsed[plugin_id] = data is not None
        if data is not None:
            inspect_parsed_json[plugin_id] = data
            current = plugins.setdefault(plugin_id, {'present': True})
            current.update(_extract_plugin_from_inspect_json(plugin_id, data))
        else:
            plugins.setdefault(plugin_id, {'present': False})

    declared_slots = _collect_slots(actual_openclaw_config)

    return {
        'raw_parse': {
            'list_json_parsed': list_parsed,
            'inspect_json_parsed': inspect_json_parsed,
        },
        'declared_slots_from_actual_config': {
            'memory': declared_slots.get('memory'),
            'contextEngine': declared_slots.get('contextEngine'),
        },
        'inventory_selected_slots': {
            'memory': selected_slots.get('memory'),
            'contextEngine': selected_slots.get('contextEngine'),
        },
        'plugins': plugins,
        'parsed_json': {
            'list': list_json,
            'inspect': inspect_parsed_json,
        },
        'group': spec.get('group'),
    }


def evaluate_runtime_architecture(spec: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    expected_memory = spec.get('memory_slot')
    expected_context = spec.get('context_engine_slot')
    declared_slots = normalized.get('declared_slots_from_actual_config') or {}
    inventory_slots = normalized.get('inventory_selected_slots') or {}
    plugins = normalized.get('plugins') or {}
    raw_parse = normalized.get('raw_parse') or {}

    checks: dict[str, Any] = {}
    blocking_reasons: list[str] = []

    checks['plugins_list_json_parsed'] = raw_parse.get('list_json_parsed') is True
    if not checks['plugins_list_json_parsed']:
        blocking_reasons.append('plugin inventory list output could not be parsed as JSON')

    inspect_expected = spec.get('inspect_plugins', []) or []
    inspect_parse = raw_parse.get('inspect_json_parsed') or {}
    checks['inspect_json_parsed'] = {pid: inspect_parse.get(pid) is True for pid in inspect_expected}
    if inspect_expected and not all(checks['inspect_json_parsed'].values()):
        missing = [pid for pid, ok in checks['inspect_json_parsed'].items() if not ok]
        blocking_reasons.append('plugin inspect output could not be parsed for: ' + ', '.join(missing))

    checks['memory_slot_matches_spec'] = declared_slots.get('memory') == expected_memory
    checks['context_engine_slot_matches_spec'] = declared_slots.get('contextEngine') == expected_context
    if not checks['memory_slot_matches_spec']:
        blocking_reasons.append(f'declared memory slot mismatch: expected {expected_memory}, got {declared_slots.get("memory")!r}')
    if not checks['context_engine_slot_matches_spec']:
        blocking_reasons.append(f'declared contextEngine slot mismatch: expected {expected_context}, got {declared_slots.get("contextEngine")!r}')

    checks['inventory_memory_slot_matches_spec'] = inventory_slots.get('memory') == expected_memory
    checks['inventory_context_engine_slot_matches_spec'] = inventory_slots.get('contextEngine') == expected_context
    if not checks['inventory_memory_slot_matches_spec']:
        blocking_reasons.append(f'inventory selected memory slot mismatch: expected {expected_memory}, got {inventory_slots.get("memory")!r}')
    if not checks['inventory_context_engine_slot_matches_spec']:
        blocking_reasons.append(f'inventory selected contextEngine slot mismatch: expected {expected_context}, got {inventory_slots.get("contextEngine")!r}')

    expected_plugins = set(inspect_expected)
    if expected_memory:
        expected_plugins.add(expected_memory)
    if expected_context and expected_context != 'legacy':
        expected_plugins.add(expected_context)

    plugin_presence: dict[str, bool] = {}
    plugin_enabled: dict[str, bool] = {}
    plugin_kind_matches: dict[str, bool] = {}
    for plugin_id in sorted(expected_plugins):
        info = plugins.get(plugin_id) or {}
        plugin_presence[plugin_id] = info.get('present') is True or plugin_id in plugins
        plugin_enabled[plugin_id] = info.get('enabled') is True
        expected_kind = None
        if plugin_id in {expected_memory, 'memory-core', 'memory-lancedb', 'memory-openviking'}:
            expected_kind = 'memory'
        if plugin_id == expected_context and expected_context not in {None, 'legacy'}:
            expected_kind = 'context-engine'
        if expected_kind is None:
            plugin_kind_matches[plugin_id] = True
        else:
            plugin_kind_matches[plugin_id] = _normalize_kind(info.get('kind')) == expected_kind

    checks['expected_plugins_present'] = plugin_presence
    checks['expected_plugins_enabled'] = plugin_enabled
    checks['expected_plugins_kind_matches'] = plugin_kind_matches
    if not all(plugin_presence.values()):
        missing = [pid for pid, ok in plugin_presence.items() if not ok]
        blocking_reasons.append('expected plugin(s) missing from inventory/inspect: ' + ', '.join(missing))
    if not all(plugin_enabled.values()):
        bad = [pid for pid, ok in plugin_enabled.items() if not ok]
        blocking_reasons.append('expected plugin(s) not enabled: ' + ', '.join(bad))
    if not all(plugin_kind_matches.values()):
        bad = [pid for pid, ok in plugin_kind_matches.items() if not ok]
        blocking_reasons.append('expected plugin kind mismatch: ' + ', '.join(bad))

    row3_proved = True
    if spec.get('group') == 'row3-openviking-minus-core':
        row3_proved = (
            declared_slots.get('memory') == 'memory-openviking'
            and declared_slots.get('contextEngine') == 'legacy'
            and inventory_slots.get('memory') == 'memory-openviking'
            and _normalize_kind((plugins.get('memory-openviking') or {}).get('kind')) == 'memory'
        )
        checks['row3_legacy_memory_path_proved'] = row3_proved
        if not row3_proved:
            blocking_reasons.append('row3 runtime did not prove legacy memory-slot path')

    row4_proved = True
    if spec.get('group') == 'row4-compat-primary':
        memory_info = plugins.get('memory-core') or {}
        ov_info = plugins.get('openviking') or {}
        row4_proved = (
            declared_slots.get('memory') == 'memory-core'
            and declared_slots.get('contextEngine') == 'openviking'
            and inventory_slots.get('memory') == 'memory-core'
            and inventory_slots.get('contextEngine') == 'openviking'
            and memory_info.get('enabled') is True
            and ov_info.get('enabled') is True
            and _normalize_kind(memory_info.get('kind')) == 'memory'
            and _normalize_kind(ov_info.get('kind')) == 'context-engine'
        )
        checks['row4_coexistence_proved'] = row4_proved
        if not row4_proved:
            blocking_reasons.append('row4 runtime did not prove memory-core + contextEngine=openviking coexistence')

    overall_passed = (
        checks['plugins_list_json_parsed']
        and all(checks['inspect_json_parsed'].values())
        and checks['memory_slot_matches_spec']
        and checks['context_engine_slot_matches_spec']
        and checks['inventory_memory_slot_matches_spec']
        and checks['inventory_context_engine_slot_matches_spec']
        and all(plugin_presence.values())
        and all(plugin_enabled.values())
        and all(plugin_kind_matches.values())
        and row3_proved
        and row4_proved
    )

    return {
        'expected': {
            'memory_slot': expected_memory,
            'context_engine_slot': expected_context,
        },
        'checks': checks,
        'overall_passed': overall_passed,
        'blocking_reasons': blocking_reasons,
        'selected_memory_slot': inventory_slots.get('memory') or declared_slots.get('memory'),
        'selected_context_engine_slot': inventory_slots.get('contextEngine') or declared_slots.get('contextEngine'),
    }
