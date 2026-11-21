"""Deterministic reference facts; no model judge or external calls."""
from __future__ import annotations

import re

from .core import digest
from .demo import _mapping_rows, table_rows


def _normal(text: str) -> str:
    return text.lower().replace('`', '').replace('**', '').replace('–', '-').replace('—', '-')


def _mentions(text: str, name: str) -> bool:
    text = re.sub(r'\b([a-z_]\w*_)([a-z0-9]+)((?:/[a-z0-9]+)+)\b',
                  lambda m: ' '.join(m[1] + s for s in [m[2], *m[3][1:].split('/')]), text)
    return bool(re.search(r'(?<![a-z0-9_])' + re.escape(name) + r'(?![a-z0-9_])', text))


def _addresses(text: str) -> set[str]:
    return set(re.findall(r'%(?:ch|mw|[iq])\d+(?:\.\d+)*', text))


def _modules(text: str) -> set[str]:
    matches = re.findall(r'\bbmx\s*(?:ddi|ddo|ami)\s*\d+[a-z0-9]*\b', text)
    return {re.sub(r'\s+', '', match) for match in matches}


def _channels(row: list[str], channel: str, device: bool) -> bool:
    channel = channel.replace('–', '-')
    pattern = re.escape(channel).replace(r'\-', r'(?:-|\.\.|to)')
    for cell in row:
        compact = re.sub(r'\s+', '', cell)
        if re.fullmatch(r'(?:(?:ch(?:annel)?s?|output|input|analoginput):?)?' + pattern, compact):
            return True
        if '-' not in channel and re.search(r'\bch(?:annel)?\s*:?\s*' + channel + r'\b', cell):
            return True
        if '-' not in channel and re.fullmatch(r'byte\s*0,?\s*bit\s*' + channel, cell):
            return True
    if device and '-' in channel:
        start, end = map(int, channel.split('-'))
        return bool(re.search(r'\b' + str(end-start+1) + r'\s+(?:di|do|ai)\b', ' '.join(row)))
    return False


def _channel_claims(row: list[str]) -> list[str]:
    claims = []
    for cell in row:
        match = re.fullmatch(r'(?:(?:ch(?:annel)?s?|output|input|analog\s+input)\s*:?\s*)?'
                             r'(\d+(?:\s*(?:-|\.\.|to)\s*\d+)?)', cell)
        if match:
            claims.append(re.sub(r'\s+', '', match[1]).replace('to', '-').replace('..', '-'))
    return claims


def _hardware_channels(text: str) -> dict[tuple[str, str], list[str]]:
    """Join only explicit slot/module/channel columns, never module capacity guesses."""
    result = {}
    header = []
    for line in text.splitlines():
        if not line.strip().startswith('|'):
            header = []
            continue
        row = table_rows(_normal(line))[0]
        if not header:
            header = row
            continue
        if 'slot' not in header or 'module' not in header:
            continue
        channel_index = next((i for i, cell in enumerate(header) if 'channel' in cell), None)
        if channel_index is None or len(row) != len(header):
            continue
        slot, modules = row[header.index('slot')], _modules(row[header.index('module')])
        if slot.isdigit() and len(modules) == 1:
            result.setdefault((slot, next(iter(modules))), []).append(row[channel_index])
    return result


def grade_mapping(answer: str, reference: str) -> dict:
    """Require reference coverage and reject contradictory row-local facts.

    Separate matched/missing/incorrect facts make partial evidence reviewable.
    Physical facts stay row-local; unrelated correct addresses cannot rescue a
    wrong mapping. Memory declarations may also be explicitly stated in prose.
    """
    expected = {}
    for row in table_rows(reference):
        if len(row) >= 7:
            expected.setdefault(row[0], row)
    rows = _mapping_rows(answer)
    physical = {name: row for name, row in expected.items() if row[5].startswith('physical')}
    hardware = _hardware_channels(answer)
    checks, facts = {}, {}

    def record(key, status, reason, evidence):
        checks[key] = status == 'matched'
        facts[key] = {'status': status, 'reason': reason,
                      'evidence_sha256': sorted({digest(text) for text in evidence})}

    for name, truth in physical.items():
        candidates = [row for row, index, _ in rows if _mentions(row[index], name)
                      and not re.search(re.escape(name) + r'[.\[]', row[index])
                      and sum(_mentions(row[index], n) for n in physical) == 1]
        valid, incorrect = [], []
        for row in candidates:
            joined = ' '.join(row)
            module = next(iter(_modules(truth[3])))
            addresses = _addresses(joined)
            # A channel address is exact, not a substring (e.g. .1 vs .10).
            address_ok = truth[2] in addresses if truth[2].startswith('%') else _mentions(joined, truth[2])
            module_ok = _modules(joined) == {module}
            channel_ok = _channels(row, truth[4], truth[5] == 'physical device ddt')
            # Slot evidence, when provided, must agree with the reference.
            slot = re.search(r'slot\s*(\d+)', truth[3])
            slots = re.findall(r'slot\s*(\d+)', joined)
            slot_ok = not slots or all(s == slot[1] for s in slots)
            claims = _channel_claims(row)
            wrong_channel = bool(claims) and any(c != truth[4].replace('–', '-') for c in claims)
            if not channel_ok and not claims and truth[5] == 'physical device ddt' and slots and slot_ok:
                linked = hardware.get((slot[1], module), [])
                channel_ok = bool(linked) and all(_channels([value], truth[4], True) for value in linked)
            wrong_address = bool(addresses - {truth[2]})
            if wrong_address or (_modules(joined) and not module_ok) or not slot_ok or wrong_channel:
                incorrect.append(joined)
            elif address_ok and module_ok and channel_ok and not re.search(r'\bunmapped\b|no physical', joined):
                valid.append(joined)
        key = 'physical:' + name
        if incorrect:
            record(key, 'incorrect', 'Conflicting address, module, slot or channel', incorrect)
        elif valid:
            record(key, 'matched', 'Signal, address/DDT, module and channel established together', valid)
        else:
            record(key, 'missing', 'Need signal, exact address/DDT, module and channel in one row', [' '.join(r) for r in candidates])

    normalized = _normal(answer)
    for name in ('current_position', 'recipe'):
        address = expected[name][2]
        candidates = [' '.join(row) for row, index, _ in rows if _mentions(row[index], name)]
        incorrect = [s for s in candidates if _addresses(s) and address not in _addresses(s)]
        # Keep the name/address association local, including parenthetical form.
        for line in normalized.splitlines():
            location = re.search(r'\b' + name + r'\b\s*(?:\(\s*)?(?:is\s+|at\s+)?(%mw\d+)\b', line)
            if location:
                candidates.append(line)
                if location[1] != address:
                    incorrect.append(line)
        valid = [s for s in candidates if address in _addresses(s)
                 and re.search(r'memory|internal|no physical|unmapped|no i/o|not physical|not i/o|not i/o-channel', s)
                 and not _modules(s) and not re.search(r'%(?:[iq]|ch)\d', s)]
        record('memory:' + name, 'incorrect' if incorrect else 'matched' if valid else 'missing',
               'Require explicit internal-memory location and classification', incorrect or valid or candidates)

    required = ('start', 'stop', 'bp0', 'bp1', 'switch0', 'measured_temp',
                'valve_a_open', 'valve_a_closed', 'valve_b_open', 'valve_b_closed',
                'conveying_screw', 'forming', 'belt_running', 'material_picked_off', 'robot_one')
    contradictions = []
    for name in required:
        candidates = [(row, unmapped) for row, index, unmapped in rows if _mentions(row[index], name)]
        bad = [' '.join(row) for row, _ in candidates
               if re.search(r'%(?:[iq]|ch)\d', ' '.join(row)) or _modules(' '.join(row))]
        good = [' '.join(row) for row, unmapped in candidates if unmapped]
        contradictions.extend(bad)
        key = 'robot_unmapped' if name == 'robot_one' else 'unmapped:' + name
        record(key, 'incorrect' if bad else 'matched' if good else 'missing',
               'Require explicit unmapped classification without hardware assignment', bad or good)
    # Check the full reference inventory, not only the required sample.
    for row, index, _ in rows:
        if any(truth[5].startswith('unmapped') and _mentions(row[index], name)
               for name, truth in expected.items()):
            joined = ' '.join(row)
            if re.search(r'%(?:[iq]|ch)\d', joined) or _modules(joined):
                contradictions.append(joined)
    record('no_false_physical_mappings', 'incorrect' if contradictions else 'matched',
           'Reference-unmapped signals must not acquire hardware assignments', sorted(set(contradictions)))
    matched = sum(checks.values())
    return {'rubric': 'demo-io-mapping-3', 'checks': checks, 'facts': facts,
            'coverage': {'matched': matched, 'required': len(checks), 'fraction': matched / len(checks)},
            'missing': [key for key, fact in facts.items() if fact['status'] == 'missing'],
            'incorrect': [key for key, fact in facts.items() if fact['status'] == 'incorrect'],
            'answer_pass': all(checks.values()),
            'limitation': 'Deterministic reference subset; unrecognized representations remain missing. '
                          'No semantic or exhaustive device-leaf verification.'}
