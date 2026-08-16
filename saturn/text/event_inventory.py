"""Build a curation inventory for the Saturn game's general event dialogue."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from util.assets import BINDING_ROOT, load_binding
from util.tokens import Named, Raw, parse_tokens


TEXT_ROOT = Path(__file__).resolve().parent
CORPUS_ROOT = TEXT_ROOT / "corpus" / "game" / "eve"
DEFAULT_OUTPUT = TEXT_ROOT / "generated" / "event_scene_inventory.json"
SCENES_PATH = TEXT_ROOT / "config" / "event_scenes.json"
GENERAL_EVENT_SOURCES = ("mesfile", "evfile_0", "evfile_1", "evfile_2")

_RECORD_FIELDS = {
    "id",
    "source_encoding",
    "output_encoding",
    "reference",
    "translation",
    "note",
}
_PHYSICAL_ID_RE = re.compile(
    r"game\.(mesfile|evfile_[012])\.m([0-9]{4})\.p([0-9]{2})\Z"
)
_PHYSICAL_GROUP_RE = re.compile(
    r"game\.(mesfile|evfile_[012])\.m[0-9]{4}\Z"
)
_IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_DOTTED_IDENTIFIER_RE = re.compile(
    r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\Z"
)
_SPEAKER_CUE_RE = re.compile(r"^([^{}\n]{1,20})：")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing JSON file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error


@dataclass(frozen=True, slots=True)
class EventPage:
    physical_id: str
    source_encoding: str
    reference: str
    asset_uses: tuple[str, ...]

    def document(self) -> dict[str, object]:
        return {
            "physical_id": self.physical_id,
            "source_encoding": self.source_encoding,
            "reference": self.reference,
            "asset_uses": list(self.asset_uses),
        }


@dataclass(frozen=True, slots=True)
class SceneAnnotation:
    scene: str
    consumer: str
    location: str | None
    story_state: str | None
    choice_structure: str | None
    call_sites: tuple[str, ...]
    note: str

    def document(self) -> dict[str, object]:
        return {
            "scene": self.scene,
            "consumer": self.consumer,
            "location": self.location,
            "story_state": self.story_state,
            "choice_structure": self.choice_structure,
            "call_sites": list(self.call_sites),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class EventMessage:
    physical_group: str
    source: str
    message: int
    pages: tuple[EventPage, ...]
    literal_speaker_cues: tuple[str, ...]
    named_tokens: tuple[str, ...]
    raw_tokens: tuple[str, ...]
    annotation: SceneAnnotation | None

    @property
    def binding_state(self) -> str:
        bound = sum(bool(page.asset_uses) for page in self.pages)
        if bound == 0:
            return "unbound"
        if bound == len(self.pages):
            return "bound"
        return "partially_bound"

    def document(self) -> dict[str, object]:
        curation = (
            self.annotation.document()
            if self.annotation is not None
            else {
                "scene": None,
                "consumer": None,
                "location": None,
                "story_state": None,
                "choice_structure": None,
                "call_sites": [],
                "note": None,
            }
        )
        return {
            "physical_group": self.physical_group,
            "source": self.source,
            "message": self.message,
            "binding_state": self.binding_state,
            "pages": [page.document() for page in self.pages],
            "evidence": {
                "literal_speaker_cues": list(self.literal_speaker_cues),
                "named_tokens": list(self.named_tokens),
                "raw_tokens": list(self.raw_tokens),
            },
            "curation": curation,
        }


def _optional_identifier(value: Any, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase identifier or null")
    return value


def _scene_annotations(path: Path | None) -> dict[str, SceneAnnotation]:
    if path is None:
        return {}
    document = _read_json(path)
    if not isinstance(document, dict) or set(document) != {"version", "scenes"}:
        raise ValueError(f"{path} must contain version and scenes")
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{path}: version must be 1")
    if not isinstance(document["scenes"], dict) or not document["scenes"]:
        raise ValueError(f"{path}.scenes must be a nonempty object")

    annotations: dict[str, SceneAnnotation] = {}
    expected = {
        "consumer",
        "physical_groups",
        "location",
        "story_state",
        "choice_structure",
        "call_sites",
        "note",
    }
    for scene, value in document["scenes"].items():
        context = f"{path}.scenes.{scene}"
        if not isinstance(scene, str) or _IDENTIFIER_RE.fullmatch(scene) is None:
            raise ValueError(f"{path}.scenes keys must be lowercase identifiers")
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f"{context} has an invalid scene annotation shape")
        consumer = value["consumer"]
        if (
            not isinstance(consumer, str)
            or _DOTTED_IDENTIFIER_RE.fullmatch(consumer) is None
        ):
            raise ValueError(f"{context}.consumer must be a dotted identifier")
        groups = value["physical_groups"]
        if not isinstance(groups, list) or not groups:
            raise ValueError(f"{context}.physical_groups must be a nonempty list")
        if not all(
            isinstance(group, str) and _PHYSICAL_GROUP_RE.fullmatch(group)
            for group in groups
        ):
            raise ValueError(f"{context}.physical_groups contains an invalid group")
        if len(groups) != len(set(groups)):
            raise ValueError(f"{context}.physical_groups contains duplicates")
        call_sites = value["call_sites"]
        if (
            not isinstance(call_sites, list)
            or not all(
                isinstance(call_site, str) and call_site
                for call_site in call_sites
            )
            or len(call_sites) != len(set(call_sites))
        ):
            raise ValueError(f"{context}.call_sites must be unique nonempty strings")
        note = value["note"]
        if not isinstance(note, str) or not note:
            raise ValueError(f"{context}.note must be nonempty text")
        annotation = SceneAnnotation(
            scene,
            consumer,
            _optional_identifier(value["location"], f"{context}.location"),
            _optional_identifier(value["story_state"], f"{context}.story_state"),
            _optional_identifier(
                value["choice_structure"], f"{context}.choice_structure"
            ),
            tuple(call_sites),
            note,
        )
        for group in groups:
            if group in annotations:
                raise ValueError(f"{path}: physical group {group} has two scenes")
            annotations[group] = annotation
    return annotations


def _binding_uses(binding_root: Path) -> dict[str, tuple[str, ...]]:
    uses: dict[str, list[str]] = defaultdict(list)
    for path in sorted(binding_root.glob("*.json")):
        binding = load_binding(path)
        asset = binding.asset.as_posix()
        for physical_id, asset_ref in binding.records.items():
            uses[physical_id].append(f"{asset}#{asset_ref}")
        for physical_id, additional in binding.additional_uses.items():
            uses[physical_id].extend(
                f"{asset}#{use.asset_ref}" for use in additional
            )
    return {
        physical_id: tuple(sorted(set(asset_uses)))
        for physical_id, asset_uses in uses.items()
    }


def _load_pages(
    source: str,
    corpus_root: Path,
    binding_uses: dict[str, tuple[str, ...]],
) -> list[tuple[int, int, EventPage]]:
    path = corpus_root / f"{source}.json"
    document = _read_json(path)
    if not isinstance(document, list):
        raise ValueError(f"{path} must contain a record list")

    pages: list[tuple[int, int, EventPage]] = []
    seen: set[str] = set()
    for index, value in enumerate(document):
        context = f"{path}[{index}]"
        if not isinstance(value, dict) or set(value) != _RECORD_FIELDS:
            raise ValueError(f"{context} is not a physical corpus record")
        physical_id = value["id"]
        match = (
            _PHYSICAL_ID_RE.fullmatch(physical_id)
            if isinstance(physical_id, str)
            else None
        )
        if match is None or match.group(1) != source:
            raise ValueError(f"{context}.id does not belong to {source}")
        if physical_id in seen:
            raise ValueError(f"{path} repeats physical ID {physical_id}")
        seen.add(physical_id)

        reference = value["reference"]
        source_encoding = value["source_encoding"]
        if not isinstance(reference, str) or not isinstance(source_encoding, str):
            raise ValueError(f"{context} text fields must be strings")
        parse_tokens(reference)
        pages.append(
            (
                int(match.group(2)),
                int(match.group(3)),
                EventPage(
                    physical_id,
                    source_encoding,
                    reference,
                    binding_uses.get(physical_id, ()),
                ),
            )
        )
    return pages


def build_inventory(
    *,
    corpus_root: Path = CORPUS_ROOT,
    binding_root: Path = BINDING_ROOT,
    scenes_path: Path | None = SCENES_PATH,
) -> dict[str, object]:
    uses = _binding_uses(binding_root)
    annotations = _scene_annotations(scenes_path)
    messages: list[EventMessage] = []

    for source in GENERAL_EVENT_SOURCES:
        grouped: dict[int, list[tuple[int, EventPage]]] = defaultdict(list)
        for message, page, record in _load_pages(source, corpus_root, uses):
            grouped[message].append((page, record))

        for message, records in sorted(grouped.items()):
            records.sort(key=lambda row: row[0])
            page_numbers = [page for page, _record in records]
            if page_numbers != list(range(len(records))):
                raise ValueError(
                    f"{source} message {message} pages are not contiguous from p00"
                )
            pages = tuple(record for _page, record in records)
            speaker_cues: set[str] = set()
            named_tokens: set[str] = set()
            raw_tokens: set[str] = set()
            for page in pages:
                cue = _SPEAKER_CUE_RE.match(page.reference)
                if cue is not None:
                    speaker_cues.add(cue.group(1))
                for token in parse_tokens(page.reference):
                    if isinstance(token, Named):
                        named_tokens.add(token.name)
                    elif isinstance(token, Raw):
                        raw_tokens.add(
                            f"{token.kind}:{token.value:0{token.width * 2}x}"
                        )
            physical_group = f"game.{source}.m{message:04d}"
            messages.append(
                EventMessage(
                    physical_group,
                    source,
                    message,
                    pages,
                    tuple(sorted(speaker_cues)),
                    tuple(sorted(named_tokens)),
                    tuple(sorted(raw_tokens)),
                    annotations.get(physical_group),
                )
            )

    physical_groups = {message.physical_group for message in messages}
    unknown_groups = set(annotations) - physical_groups
    if unknown_groups:
        raise ValueError(
            f"{scenes_path}: scene annotations name unknown physical groups "
            f"{sorted(unknown_groups)}"
        )

    page_count = sum(len(message.pages) for message in messages)
    bound_pages = sum(
        bool(page.asset_uses)
        for message in messages
        for page in message.pages
    )
    curated_messages = sum(message.annotation is not None for message in messages)
    scene_count = len(
        {
            message.annotation.scene
            for message in messages
            if message.annotation is not None
        }
    )
    return {
        "version": 1,
        "scope": "saturn.general_event_dialogue",
        "summary": {
            "sources": len(GENERAL_EVENT_SOURCES),
            "messages": len(messages),
            "pages": page_count,
            "bound_pages": bound_pages,
            "unbound_pages": page_count - bound_pages,
            "curated_scenes": scene_count,
            "curated_messages": curated_messages,
            "unclassified_messages": len(messages) - curated_messages,
        },
        "messages": [message.document() for message in messages],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"report path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    document = build_inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = document["summary"]
    print(
        f"wrote {summary['messages']:,} messages / {summary['pages']:,} pages "
        f"with {summary['curated_scenes']:,} curated scene(s) and "
        f"{summary['bound_pages']:,} bound page(s) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
