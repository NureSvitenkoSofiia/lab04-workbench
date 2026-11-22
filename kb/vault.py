"""Модуль читання та обходу сховища Obsidian для JarLight."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


@dataclass
class VaultNote:
    """Представлення нотатки зі сховища Obsidian."""

    rel_path: str
    title: str
    tags: list[str] = field(default_factory=list)
    source: str = ""
    updated: str = ""
    content: str = ""
    wiki_links: list[str] = field(default_factory=list)


class ObsidianVault:
    """Клієнт доступу до сховища Obsidian із захистом від path traversal."""

    def __init__(self, vault_path: str | Path):
        self.vault_path = Path(vault_path).resolve()
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Сховище не знайдено: {self.vault_path}")

    def list_notes(self) -> list[Path]:
        """Повертає список усіх .md файлів у сховищі (ігноруючи приховані папки)."""
        notes = []
        for path in self.vault_path.rglob("*.md"):
            parts = path.relative_to(self.vault_path).parts
            if any(part.startswith(".") for part in parts):
                continue
            notes.append(path)
        return sorted(notes)

    def read_note(self, rel_path: str) -> VaultNote:
        """Безпечно зчитує нотатку за відносним шляхом із захистом від Path Traversal."""
        cleaned = rel_path.strip().replace("\\", "/")
        if not cleaned.endswith(".md"):
            cleaned += ".md"

        target_path = (self.vault_path / cleaned).resolve()

        try:
            target_path.relative_to(self.vault_path)
        except ValueError:
            raise PermissionError(f"Заборонено доступ поза межами сховища: {rel_path}")

        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"Нотатку не знайдено: {rel_path}")

        post = frontmatter.load(target_path)
        metadata = post.metadata or {}

        raw_content = post.content
        wiki_links = [
            m.group(1).split("|")[0].split("#")[0].strip()
            for m in re.finditer(r"\[\[([^\]]+)\]\]", raw_content)
        ]

        title = metadata.get("title") or target_path.stem

        return VaultNote(
            rel_path=str(target_path.relative_to(self.vault_path)).replace("\\", "/"),
            title=title,
            tags=metadata.get("tags") or [],
            source=str(metadata.get("source") or ""),
            updated=str(metadata.get("updated_at") or metadata.get("updated") or ""),
            content=raw_content,
            wiki_links=wiki_links,
        )
