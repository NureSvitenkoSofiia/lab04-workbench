"""Модульні тести експорту артефактів Unity і захисту сховища Obsidian."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from workbench.exporters import (
    save_to_vault,
    to_bundle_zip,
    to_draft_pr_md,
    to_level_preset_json,
    to_unity_nunit_tests,
)


def test_exports_draft_pr_nunit_and_preset_json() -> None:
    state = {
        "report": "# draft: [JL-24] PrismSplitter",
        "implementation": {
            "unity_nunit_tests": "[Test] public void Split() { Assert.AreEqual(3, 3); }",
            "level_preset_json": '{"levelId": "JL-24", "parMoves": 7}',
        },
    }
    assert to_draft_pr_md(state).startswith("# draft:")
    nunit = to_unity_nunit_tests(state)
    assert "using NUnit.Framework;" in nunit
    assert "[Test]" in nunit
    preset = to_level_preset_json(state)
    assert '"levelId": "JL-24"' in preset
    bundle = to_bundle_zip("jl-24", to_draft_pr_md(state), nunit, preset)
    with zipfile.ZipFile(io.BytesIO(bundle), "r") as zf:
        assert set(zf.namelist()) == {
            "jl-24_draft_pr.md",
            "jl-24_FeatureTests.cs",
            "jl-24_preset.json",
        }


def test_save_to_vault_never_overwrites_existing_note(tmp_path: Path) -> None:
    p1 = save_to_vault(tmp_path, "first", "JL-24 Prism")
    p2 = save_to_vault(tmp_path, "second", "JL-24 Prism")
    assert p1.name == "JL-24 Prism.md"
    assert p2.name == "JL-24 Prism (2).md"
    assert p1.read_text(encoding="utf-8") == "first"


def test_save_to_vault_blocks_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_to_vault(tmp_path, "hack", "Note", folder="../outside")
