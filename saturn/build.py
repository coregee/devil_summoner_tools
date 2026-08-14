"""Run a configured Saturn translation build profile."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from rom.util.catalog import load_catalog

SATURN_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = SATURN_ROOT / "build_config.json"


@dataclass(frozen=True)
class Step:
    id: str
    description: str
    type: str
    script: Path | None = None
    arguments: tuple[str, ...] = ()
    check_arguments: tuple[str, ...] | None = None
    files: tuple[tuple[Path, Path], ...] = ()


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    steps: tuple[str, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class BuildConfig:
    steps: tuple[Step, ...]
    profiles: dict[str, Profile]
    disc_outputs: dict[str, Path]


def relative_path(value: object, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be nonempty text")
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{context} must be relative")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"{context} contains an unsafe path component")
    return Path(*posix.parts)


def string_list(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{context} must be an array of strings")
    return tuple(value)


def load_step(row: object, index: int) -> Step:
    context = f"steps[{index}]"
    if not isinstance(row, dict):
        raise ValueError(f"{context} must be an object")
    step_id = row.get("id")
    description = row.get("description")
    step_type = row.get("type")
    if not isinstance(step_id, str) or not step_id:
        raise ValueError(f"{context}.id must be nonempty text")
    if not isinstance(description, str) or not description:
        raise ValueError(f"{context}.description must be nonempty text")

    if step_type == "python":
        if set(row) != {
            "id",
            "description",
            "type",
            "script",
            "arguments",
            "check_arguments",
        }:
            raise ValueError(f"{context}: malformed python step")
        check_value = row["check_arguments"]
        check_arguments = (
            None
            if check_value is None
            else string_list(check_value, f"{context}.check_arguments")
        )
        return Step(
            step_id,
            description,
            step_type,
            script=relative_path(row["script"], f"{context}.script"),
            arguments=string_list(row["arguments"], f"{context}.arguments"),
            check_arguments=check_arguments,
        )

    if step_type == "copy":
        if set(row) != {"id", "description", "type", "files"}:
            raise ValueError(f"{context}: malformed copy step")
        file_rows = row["files"]
        if not isinstance(file_rows, list) or not file_rows:
            raise ValueError(f"{context}.files must be a nonempty array")
        files = []
        for file_index, file_row in enumerate(file_rows):
            file_context = f"{context}.files[{file_index}]"
            if not isinstance(file_row, dict) or set(file_row) != {
                "source",
                "destination",
            }:
                raise ValueError(f"{file_context} must contain source and destination")
            files.append(
                (
                    relative_path(file_row["source"], f"{file_context}.source"),
                    relative_path(
                        file_row["destination"], f"{file_context}.destination"
                    ),
                )
            )
        return Step(step_id, description, step_type, files=tuple(files))

    raise ValueError(f"{context}.type must be python or copy")


def load_config(path: Path = CONFIG_PATH) -> BuildConfig:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "version",
        "steps",
        "profiles",
    }:
        raise ValueError(f"{path}: expected version, steps, and profiles")
    if document["version"] != 1:
        raise ValueError(f"{path}: unsupported version")

    disc_outputs = {}
    for disc_id, disc in load_catalog().items():
        cue = relative_path(disc.cue, f"rom/discs.json.discs.{disc_id}.cue")
        if len(cue.parts) != 1 or cue.suffix.casefold() != ".cue":
            raise ValueError(
                f"rom/discs.json.discs.{disc_id}.cue must be a CUE filename"
            )
        disc_outputs[disc_id] = Path("rom") / "build" / disc_id / cue

    step_rows = document["steps"]
    if not isinstance(step_rows, list) or not step_rows:
        raise ValueError(f"{path}: steps must be a nonempty array")
    steps = tuple(load_step(row, index) for index, row in enumerate(step_rows))
    step_ids = [step.id for step in steps]
    if len({step_id.casefold() for step_id in step_ids}) != len(step_ids):
        raise ValueError(f"{path}: duplicate step id")

    profile_rows = document["profiles"]
    if not isinstance(profile_rows, dict) or not profile_rows:
        raise ValueError(f"{path}: profiles must be a nonempty object")
    profiles = {}
    for name, row in profile_rows.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(row, dict)
            or set(row) != {"description", "steps", "outputs"}
            or not isinstance(row["description"], str)
            or not row["description"]
        ):
            raise ValueError(f"{path}: malformed profile {name!r}")
        profile_steps = string_list(row["steps"], f"profiles.{name}.steps")
        if len(set(profile_steps)) != len(profile_steps):
            raise ValueError(f"profiles.{name}: duplicate step")
        unknown = [step_id for step_id in profile_steps if step_id not in step_ids]
        if unknown:
            raise ValueError(f"profiles.{name}: unknown steps {unknown}")
        profile_outputs = string_list(row["outputs"], f"profiles.{name}.outputs")
        if not profile_outputs:
            raise ValueError(f"profiles.{name}: outputs cannot be empty")
        if len(set(profile_outputs)) != len(profile_outputs):
            raise ValueError(f"profiles.{name}: duplicate output")
        unknown_outputs = [
            disc_id for disc_id in profile_outputs if disc_id not in disc_outputs
        ]
        if unknown_outputs:
            raise ValueError(
                f"profiles.{name}: unknown output discs {unknown_outputs}; "
                f"choose from {list(disc_outputs)}"
            )
        profiles[name] = Profile(
            name,
            row["description"],
            profile_steps,
            profile_outputs,
        )
    if "default" not in profiles:
        raise ValueError(f"{path}: default profile is missing")
    if profiles["default"].steps != tuple(step_ids):
        raise ValueError(f"{path}: default profile must execute every step in order")

    return BuildConfig(steps, profiles, disc_outputs)


def step_command(step: Step, check: bool) -> list[str] | None:
    assert step.script is not None
    arguments = step.check_arguments if check else step.arguments
    if arguments is None:
        return None
    return [sys.executable, "-B", str(step.script), *arguments]


def run_python(step: Step, check: bool) -> None:
    command = step_command(step, check)
    if command is None:
        print("skipped (write-only setup step)")
        return
    result = subprocess.run(command, cwd=SATURN_ROOT, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def run_copy(step: Step, check: bool) -> None:
    for source_relative, destination_relative in step.files:
        source = SATURN_ROOT / source_relative
        destination = SATURN_ROOT / destination_relative
        if not source.is_file():
            raise ValueError(f"copy source is missing: {source}")
        if check:
            if (
                not destination.is_file()
                or source.read_bytes() != destination.read_bytes()
            ):
                raise ValueError(f"installed file is missing or stale: {destination}")
            print(f"verified {destination_relative.as_posix()}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        print(
            f"installed {source_relative.as_posix()} -> {destination_relative.as_posix()}"
        )


def run_step(step: Step, check: bool) -> None:
    print(f"\n== {step.id}: {step.description} ==", flush=True)
    if step.type == "python":
        run_python(step, check)
    else:
        run_copy(step, check)


def print_plan(config: BuildConfig, profile: Profile, check: bool) -> None:
    steps = {step.id: step for step in config.steps}
    print(f"Profile: {profile.name} - {profile.description}")
    print(f"Mode: {'check' if check else 'build'}")
    for index, step_id in enumerate(profile.steps, 1):
        step = steps[step_id]
        if step.type == "python":
            command = step_command(step, check)
            action = "skip" if command is None else " ".join(command)
        else:
            action = f"{'verify' if check else 'copy'} {len(step.files)} file(s)"
        print(f"{index}. {step.id}: {action}")
    print("Outputs:")
    for disc_id in profile.outputs:
        print(f"  [{disc_id}] {SATURN_ROOT / config.disc_outputs[disc_id]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="?", default="default", help="build profile")
    parser.add_argument("--check", action="store_true", help="verify existing outputs")
    parser.add_argument(
        "--plan", action="store_true", help="show steps without running"
    )
    parser.add_argument(
        "--list-steps", action="store_true", help="list configured steps"
    )
    parser.add_argument(
        "--list-profiles", action="store_true", help="list configured profiles"
    )
    arguments = parser.parse_args()
    try:
        config = load_config()
        if arguments.list_steps:
            for step in config.steps:
                print(f"{step.id}: {step.description}")
            return
        if arguments.list_profiles:
            for profile in config.profiles.values():
                print(f"{profile.name}: {profile.description}")
            return
        try:
            profile = config.profiles[arguments.profile]
        except KeyError:
            parser.error(f"unknown profile: {arguments.profile}")
        if arguments.plan:
            print_plan(config, profile, arguments.check)
            return

        steps = {step.id: step for step in config.steps}
        for step_id in profile.steps:
            run_step(steps[step_id], arguments.check)
        outputs = [
            (disc_id, SATURN_ROOT / config.disc_outputs[disc_id])
            for disc_id in profile.outputs
        ]
        for disc_id, output in outputs:
            if not output.is_file():
                raise ValueError(f"{disc_id} build output is missing: {output}")
        action = "verified" if arguments.check else "built"
        print(f"\nPatched discs {action}:")
        for disc_id, output in outputs:
            print(f"  [{disc_id}] {output}")
    except (json.JSONDecodeError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
