from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import MappingProxyType

TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

import extract  # noqa: E402
from util.config import load_config  # noqa: E402
from util.containers import Region, extract_source  # noqa: E402
from util.sources import (  # noqa: E402
    SourceManifest,
    SourceSpec,
    load_manifest,
    manifest_path,
)


class GameInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.batch = extract.build_batch("game")

    def test_complete_inventory_snapshot(self) -> None:
        self.assertEqual(self.batch.source_count, 51)
        self.assertEqual(self.batch.record_count, 15_613)
        self.assertEqual(len(self.batch.rendered), 51)
        self.assertEqual(
            {path.as_posix() for path in self.batch.composed_files},
            {"LOAD.BIN", "SAVE.BIN"},
        )

        rows = [
            row
            for rendered in self.batch.rendered.values()
            for row in json.loads(rendered)
        ]
        ids = [row["id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            sum("/eve/" in f"/{path.as_posix()}" for path in self.batch.rendered), 21
        )
        self.assertEqual(sum(row_id.startswith("game.") for row_id in ids), 15_613)

        eve_rows = [
            row
            for path, rendered in self.batch.rendered.items()
            if path.parts[0] == "eve"
            for row in json.loads(rendered)
        ]
        self.assertEqual(len(eve_rows), 12_711)
        self.assertEqual(len(rows) - len(eve_rows), 2_902)
        self.assertGreater(sum("{GLYPH:" in row["reference"] for row in rows), 0)
        self.assertGreater(sum("{OP:" in row["reference"] for row in rows), 0)
        self.assertFalse(any("{OP:8002}" in row["reference"] for row in rows))

    def test_known_exceptions_and_non_deduplication(self) -> None:
        shops = {
            row["id"]: row
            for row in json.loads(
                self.batch.rendered[PurePosixPath("eve/shopsmp.json")]
            )
        }
        self.assertNotIn("game.shopsmp.m0096.p00", shops)
        self.assertEqual(
            shops["game.shopsmp.m0004.p00"]["source_encoding"],
            "game_font16_event_space",
        )
        self.assertEqual(
            shops["game.shopsmp.m0097.p00"]["source_encoding"],
            "game_font12_event_space",
        )
        self.assertEqual(
            shops["game.shopsmp.m0137.p00"]["source_encoding"],
            "game_font12_event_space",
        )
        self.assertEqual(
            shops["game.shopsmp.m0267.p00"]["source_encoding"],
            "game_font12_16_event_skip",
        )

        evfile_0 = {
            row["id"]: row
            for row in json.loads(
                self.batch.rendered[PurePosixPath("eve/evfile_0.json")]
            )
        }
        self.assertEqual(
            evfile_0["game.evfile_0.m0029.p00"]["source_encoding"],
            "game_font16_event_space",
        )

        dungeon = json.loads(
            self.batch.rendered[PurePosixPath("fixed/dungeon_locations.json")]
        )
        self.assertEqual(len(dungeon), 144)
        self.assertEqual(len({row["id"] for row in dungeon}), 144)
        self.assertLess(len({row["reference"] for row in dungeon}), 144)

        name_rows = json.loads(
            self.batch.rendered[PurePosixPath("addressed/name_static.json")]
        )
        self.assertEqual(len(name_rows), 19)
        fork_ids = {row["id"] for row in name_rows if row["id"].count(".") == 3}
        self.assertEqual(
            fork_ids,
            {
                "game.name_static.o020b78.prompt_first",
                "game.name_static.o020b78.prompt_last",
                "game.name_static.o020bc8.prompt_city",
                "game.name_static.o020bc8.prompt_ward",
                "game.name_static.o020cb8.prompt_occupation",
                "game.name_static.o020cb8.label_occupation",
            },
        )

    def test_checked_corpus_is_current(self) -> None:
        extract.publish_batch(
            self.batch,
            extract.CORPUS_ROOT / "game",
            check=True,
        )


class CompendiumInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(manifest_path("compendium"))
        cls.batch = extract.build_batch("compendium")
        cls.rows = json.loads(cls.batch.rendered[PurePosixPath("profiles.json")])

    def test_complete_profile_inventory(self) -> None:
        absent = {
            0x105,
            0x106,
            0x107,
            0x108,
            0x109,
            0x10D,
            0x10E,
            0x117,
            0x122,
            0x123,
            0x129,
        }
        expected_files = tuple(
            f"dvl_{value:03x}" for value in range(1, 0x130) if value not in absent
        )
        self.assertEqual(tuple(self.manifest.files), expected_files)
        self.assertTrue(
            all(spec.size == 0x781DC for spec in self.manifest.files.values())
        )
        self.assertTrue(
            all(spec.owned_sha256 is not None for spec in self.manifest.files.values())
        )
        self.assertEqual(self.batch.source_count, 1)
        self.assertEqual(self.batch.record_count, 876)
        self.assertEqual(len(self.batch.rendered), 1)

        ids = [row["id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["reference"] for row in self.rows))
        self.assertTrue(
            all(
                row["source_encoding"] == "compendium_font16_plain_skip"
                for row in self.rows
            )
        )
        self.assertEqual(
            self.rows[0]["id"], "compendium.profiles.dvl_001.o078000.origin"
        )
        self.assertEqual(self.rows[0]["reference"], "インド")
        self.assertEqual(
            self.rows[-1]["id"],
            "compendium.profiles.dvl_12f.o07808e.detail",
        )
        self.assertIn("compendium.profiles.dvl_112.o078000.origin", ids)

    def test_profile_font_mapping_is_complete_and_lossless(self) -> None:
        catalog = load_config()
        self.assertEqual(len(catalog.alphabets["compendium_font16"].glyphs), 1_703)
        raw_codes = [
            code
            for row in self.rows
            for code in re.findall(r"\{GLYPH:([0-9a-f]{4})\}", row["reference"])
        ]
        self.assertEqual(len(raw_codes), 29)
        self.assertEqual(
            set(raw_codes),
            {"0026", "0029", "002d", "002f", "026e", "0656"},
        )
        self.assertFalse(any("{OP:" in row["reference"] for row in self.rows))

    def test_profile_text_aggregate_identities(self) -> None:
        tails = hashlib.sha256()
        fields = {
            "origin": hashlib.sha256(),
            "summary": hashlib.sha256(),
            "detail": hashlib.sha256(),
        }
        root = extract.ROM_ROOT / "extracted" / "compendium"
        for spec in self.manifest.files.values():
            data = root.joinpath(*spec.path.parts).read_bytes()
            tails.update(data[0x78000:0x781DC])
            fields["origin"].update(data[0x78000:0x7801E])
            fields["summary"].update(data[0x7801E:0x7808E])
            fields["detail"].update(data[0x7808E:0x781DC])
        self.assertEqual(
            tails.hexdigest(),
            "132a0ff56c3768318c231251586398dca8e405600ac9a7f127f2358a38265c27",
        )
        self.assertEqual(
            {name: digest.hexdigest() for name, digest in fields.items()},
            {
                "origin": (
                    "a55f1c4effa4415b0c9a907d3cb4fe6198b8b2a433050fff376500638a92d9a8"
                ),
                "summary": (
                    "aa5f2127b3a3da457481824d63fc592160860fa6878d9ed76670b9b0f73bc536"
                ),
                "detail": (
                    "b99e9660a8ecb4a9f630aaa1d6533601aab522c38b6e57246f78bfeedb6a2135"
                ),
            },
        )

    def test_profile_text_composes_with_visual_changes(self) -> None:
        file_id = "dvl_001"
        spec = self.manifest.files[file_id]
        path = extract.ROM_ROOT / "extracted" / "compendium" / spec.path
        stock = path.read_bytes()
        single = SourceManifest(
            "compendium",
            self.manifest.track_sha256,
            MappingProxyType({file_id: spec}),
            (),
        )
        regions = (Region(file_id, 0x78000, 0x781DC),)

        visual_change = bytearray(stock)
        visual_change[0] ^= 1
        self.assertEqual(
            extract._verify_sources(single, {file_id: bytes(visual_change)}, regions),
            (spec.path,),
        )

        text_change = bytearray(stock)
        text_change[0x78000] ^= 1
        with self.assertRaisesRegex(ValueError, "owned text SHA-256"):
            extract._verify_sources(single, {file_id: bytes(text_change)}, regions)

    def test_checked_corpus_is_current(self) -> None:
        extract.publish_batch(
            self.batch,
            extract.CORPUS_ROOT / "compendium",
            check=True,
        )


class CorpusMergeTests(unittest.TestCase):
    def test_translation_and_note_are_the_only_retained_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            corpus_root = Path(raw_directory)
            initial = extract.build_batch("game", corpus_root=corpus_root)
            extract.publish_batch(initial, corpus_root, check=False)

            path = corpus_root / "eve" / "mesfile.json"
            rows = json.loads(path.read_text(encoding="utf-8"))
            rows[0]["translation"] = "Test translation"
            rows[0]["note"] = "Context survives"
            path.write_bytes(
                (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            )

            refreshed = extract.build_batch("game", corpus_root=corpus_root)
            expected_rows = json.loads(
                refreshed.rendered[PurePosixPath("eve/mesfile.json")]
            )
            self.assertEqual(expected_rows[0]["translation"], "Test translation")
            self.assertEqual(expected_rows[0]["note"], "Context survives")
            extract.publish_batch(refreshed, corpus_root, check=True)

            stale = path.read_bytes().replace(
                rows[0]["reference"].encode("utf-8"),
                b"stale reference",
                1,
            )
            path.write_bytes(stale)
            before = path.read_bytes()
            stale_batch = extract.build_batch("game", corpus_root=corpus_root)
            with self.assertRaisesRegex(ValueError, "corpus is not current"):
                extract.publish_batch(stale_batch, corpus_root, check=True)
            self.assertEqual(path.read_bytes(), before)

    def test_orphaned_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            corpus_root = Path(raw_directory)
            path = corpus_root / "eve" / "mesfile.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "game.missing.p0000",
                            "source_encoding": "ascii",
                            "output_encoding": "",
                            "reference": "missing",
                            "translation": "",
                            "note": "",
                        }
                    ],
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "orphaned record ids"):
                extract.build_batch("game", corpus_root=corpus_root)

    def test_duplicate_corpus_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            corpus_root = Path(raw_directory)
            path = corpus_root / "eve" / "mesfile.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                '[{"translation":"first","translation":"second"}]',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                extract._load_existing(corpus_root)


class ContainerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_config()

    def extract(
        self,
        config: dict[str, object],
        data: bytes = b"AB",
        *,
        blobs: dict[str, bytes] | None = None,
    ):
        source = SourceSpec(
            "sample",
            PurePosixPath("sample.json"),
            MappingProxyType(config),
        )
        selected_blobs = {"sample_file": data} if blobs is None else blobs
        return extract_source(source, selected_blobs, self.catalog, "game")

    def test_fixed_ids_are_physical_and_ignore_block_order(self) -> None:
        blocks = [
            {"base": "0x0", "count": 1, "stride": "0x1"},
            {"base": "0x1", "count": 1, "stride": "0x1"},
        ]
        common = {
            "type": "fixed_records",
            "file": "sample_file",
            "fields": [
                {
                    "name": "text",
                    "offset": "0x0",
                    "units": 1,
                    "source_encoding": "ascii",
                    "framing": {"type": "none"},
                }
            ],
        }
        forward = self.extract({**common, "blocks": blocks})
        reverse = self.extract({**common, "blocks": list(reversed(blocks))})
        self.assertEqual(
            {record.reference: record.id for record in forward.records},
            {record.reference: record.id for record in reverse.records},
        )
        self.assertEqual(
            {record.id for record in forward.records},
            {"game.sample.o000000.text", "game.sample.o000001.text"},
        )

    def test_addressed_table_ids_ignore_table_order(self) -> None:
        def table(name: str, base: str) -> dict[str, object]:
            return {
                "name": name,
                "count": 1,
                "framing": {"type": "none"},
                "require_identical_bytes": False,
                "locations": [{"base": base, "stride": "0x1", "units": 1}],
            }

        tables = [table("alpha", "0x0"), table("beta", "0x1")]
        common = {
            "type": "addressed",
            "file": "sample_file",
            "default_source_encoding": "ascii",
            "records": [],
        }
        forward = self.extract({**common, "tables": tables})
        reverse = self.extract({**common, "tables": list(reversed(tables))})
        self.assertEqual(
            {record.reference: record.id for record in forward.records},
            {record.reference: record.id for record in reverse.records},
        )
        self.assertEqual(
            {record.id for record in forward.records},
            {"game.sample.alpha.r0000", "game.sample.beta.r0000"},
        )

    def test_fixed_file_set_ids_ignore_file_order(self) -> None:
        common = {
            "type": "fixed_records",
            "blocks": [{"base": "0x0", "count": 1, "stride": "0x1"}],
            "fields": [
                {
                    "name": "text",
                    "offset": "0x0",
                    "units": 1,
                    "source_encoding": "ascii",
                    "framing": {"type": "none"},
                }
            ],
        }
        blobs = {"first_file": b"A", "second_file": b"B"}
        forward = self.extract(
            {**common, "files": ["first_file", "second_file"]},
            blobs=blobs,
        )
        reverse = self.extract(
            {**common, "files": ["second_file", "first_file"]},
            blobs=blobs,
        )
        self.assertEqual(
            {record.reference: record.id for record in forward.records},
            {record.reference: record.id for record in reverse.records},
        )
        self.assertEqual(
            {record.id for record in forward.records},
            {
                "game.sample.first_file.o000000.text",
                "game.sample.second_file.o000000.text",
            },
        )

    def test_overlapping_fixed_and_addressed_records_are_rejected(self) -> None:
        fixed = {
            "type": "fixed_records",
            "file": "sample_file",
            "blocks": [
                {"base": "0x0", "count": 1, "stride": "0x1"},
                {"base": "0x0", "count": 1, "stride": "0x1"},
            ],
            "fields": [
                {
                    "name": "text",
                    "offset": "0x0",
                    "units": 1,
                    "source_encoding": "ascii",
                    "framing": {"type": "none"},
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "fixed fields overlap"):
            self.extract(fixed)

        def record(name: str, offset: str) -> dict[str, object]:
            return {
                "name": name,
                "source_encoding": "ascii",
                "framing": {"type": "none"},
                "join": "none",
                "locations": [{"spans": [{"offset": offset, "units": 2}]}],
            }

        addressed = {
            "type": "addressed",
            "file": "sample_file",
            "default_source_encoding": "ascii",
            "tables": [],
            "records": [record("first", "0x0"), record("second", "0x1")],
        }
        with self.assertRaisesRegex(ValueError, "overlaps"):
            self.extract(addressed, b"ABC")

    def test_cross_source_overlap_is_rejected(self) -> None:
        claims: dict[str, list[tuple[int, int, str]]] = {}
        extract._claim_source_regions(claims, (Region("file", 0, 2),), "first")
        with self.assertRaisesRegex(ValueError, "overlaps first"):
            extract._claim_source_regions(
                claims,
                (Region("file", 1, 3),),
                "second",
            )


class StrictManifestTests(unittest.TestCase):
    def test_duplicate_json_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "manifest.json"
            path.write_text('{"version": 1, "version": 1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
