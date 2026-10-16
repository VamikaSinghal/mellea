# Copyright IBM Corp. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Keep the hook reference in `docs/docs/concepts/plugins.mdx` in sync with `HookType`.

The page presents itself as exhaustive ("all N hook types", "N hook categories"),
so it must not drift from the enum (#1743). These tests parse the page and check:

- the overview bullet list, the "Hook types reference" headings, and the payload
  policy table each name every `HookType` value exactly once, and nothing else
- the hook counts and the category count quoted in prose match the enum
- every documented payload field exists on the hook's payload model
- the documented writable fields match `MELLEA_HOOK_PAYLOAD_POLICIES`
"""

import pathlib
import re
from typing import cast

import pytest
from pydantic import BaseModel

pytest.importorskip("cpex", reason="cpex not installed")

from mellea.plugins import HookType
from mellea.plugins.policies import MELLEA_HOOK_PAYLOAD_POLICIES
from mellea.plugins.types import _build_hook_registry

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGINS_DOC = REPO_ROOT / "docs" / "docs" / "concepts" / "plugins.mdx"

OBSERVE_ONLY = "*(observe-only)*"

_WORD_NUMBERS = {
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


@pytest.fixture(scope="module")
def doc_text() -> str:
    return PLUGINS_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def reference_section(doc_text: str) -> str:
    """The `## Hook types reference` section, up to the next H2."""
    match = re.search(
        r"^## Hook types reference\n(.*?)(?=^## )", doc_text, re.DOTALL | re.MULTILINE
    )
    assert match is not None, "`## Hook types reference` section not found"
    return match.group(1)


@pytest.fixture(scope="module")
def hook_entries(reference_section: str) -> dict[str, str]:
    """Map each `#### hook_name` heading to the text of its entry."""
    parts = re.split(r"^#### `([a-z_]+)`\n", reference_section, flags=re.MULTILINE)
    # parts[0] is the preamble; then alternating (name, body).
    names = parts[1::2]
    bodies = parts[2::2]
    assert len(names) == len(set(names)), f"duplicate hook headings: {names}"
    return dict(zip(names, bodies))


@pytest.fixture(scope="module")
def policy_table(reference_section: str) -> dict[str, str]:
    """Map each row of the `Hook payload policy table` to its writable-fields cell."""
    match = re.search(
        r"^### Hook payload policy table\n(.*?)(?=^### |\Z)",
        reference_section,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "`### Hook payload policy table` not found"
    rows = re.findall(r"^\| `([a-z_]+)` \| (.+?) \|$", match.group(1), re.MULTILINE)
    names = [name for name, _ in rows]
    assert len(names) == len(set(names)), f"duplicate policy rows: {names}"
    return dict(rows)


def _backticked(text: str) -> list[str]:
    """Return the backticked names on a line, ignoring parenthesized asides."""
    return re.findall(r"`([a-z_]+)`", re.sub(r"\([^)]*\)", "", text))


def _field_line(entry: str, label: str) -> str:
    match = re.search(rf"^\*\*{label}:\*\* (.+)$", entry, re.MULTILINE)
    assert match is not None, f"`**{label}:**` line missing"
    return match.group(1)


ALL_HOOKS = {ht.value for ht in HookType}


class TestOverview:
    def test_overview_lists_every_hook_once(self, doc_text: str):
        match = re.search(
            r"^Plugins are organized into (\w+) hook categories:\n\n((?:- .+\n)+)",
            doc_text,
            re.MULTILINE,
        )
        assert match is not None, "overview category list not found"
        listed = [
            name
            for bullet in match.group(2).splitlines()
            for name in re.findall(r"`([a-z_]+)`", bullet)
        ]
        assert sorted(listed) == sorted(ALL_HOOKS)

    def test_category_count_matches_reference_sections(
        self, doc_text: str, reference_section: str
    ):
        match = re.search(r"organized into (\w+) hook categories", doc_text)
        assert match is not None
        categories = re.findall(
            r"^### (?!Hook payload policy table)", reference_section, re.MULTILINE
        )
        assert _WORD_NUMBERS[match.group(1)] == len(categories)

    def test_hook_count_in_api_reference(self, doc_text: str):
        match = re.search(r"Enum with all (\d+) hook types", doc_text)
        assert match is not None, "`Enum with all N hook types` not found"
        assert int(match.group(1)) == len(HookType)


class TestHookTypesReference:
    def test_every_hook_has_exactly_one_entry(self, hook_entries: dict[str, str]):
        assert set(hook_entries) == ALL_HOOKS

    def test_entries_follow_enum_order(self, hook_entries: dict[str, str]):
        assert list(hook_entries) == [ht.value for ht in HookType]

    @pytest.mark.parametrize("hook_type", list(HookType), ids=lambda ht: ht.value)
    def test_payload_fields_exist(self, hook_type: HookType, hook_entries):
        payload_cls = cast(type[BaseModel], _build_hook_registry()[hook_type.value][0])
        documented = _backticked(
            _field_line(hook_entries[hook_type.value], "Payload fields")
        )
        assert documented, "no payload fields documented"
        unknown = set(documented) - set(payload_cls.model_fields)
        assert not unknown, (
            f"documented fields missing on {payload_cls.__name__}: {unknown}"
        )

    @pytest.mark.parametrize("hook_type", list(HookType), ids=lambda ht: ht.value)
    def test_writable_fields_match_policy(self, hook_type: HookType, hook_entries):
        line = _field_line(hook_entries[hook_type.value], "Writable fields")
        policy = MELLEA_HOOK_PAYLOAD_POLICIES.get(hook_type.value)
        if policy is None:
            assert line == OBSERVE_ONLY
        else:
            assert set(_backticked(line)) == set(policy.writable_fields)


class TestPolicyTable:
    def test_table_lists_every_hook_once(self, policy_table: dict[str, str]):
        assert set(policy_table) == ALL_HOOKS

    @pytest.mark.parametrize("hook_type", list(HookType), ids=lambda ht: ht.value)
    def test_row_matches_policy(self, hook_type: HookType, policy_table):
        cell = policy_table[hook_type.value]
        policy = MELLEA_HOOK_PAYLOAD_POLICIES.get(hook_type.value)
        if policy is None:
            assert cell == OBSERVE_ONLY
        else:
            assert set(_backticked(cell)) == set(policy.writable_fields)
