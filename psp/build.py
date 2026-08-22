"""Run a configured PSP translation build profile."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

if __package__ in {None, ""}:
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

from psp.rom.util.catalog import load_catalog


PSP_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PSP_ROOT / "build_config.json"


@dataclass(frozen=True, slots=True)
class Step:
    id: str
    description: str
    script: Path
    arguments: tuple[str, ...]
    check_arguments: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    description: str
    steps: tuple[str, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuildConfig:
    steps: tuple[Step, ...]
    profiles: dict[str, Profile]
    disc_outputs: dict[str, Path]


def _relative_path(value: object, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be nonempty text")
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{context} must be relative")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"{context} contains an unsafe path component")
    return Path(*posix.parts)


def _strings(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{context} must be an array of strings")
    return tuple(value)


def load_config(path: Path = CONFIG_PATH) -> BuildConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP build configuration: {path}") from error
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "steps", "profiles"}
        or document["version"] != 1
    ):
        raise ValueError(f"{path}: unsupported PSP build configuration")
    raw_steps = document["steps"]
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError(f"{path}: steps must be a nonempty array")
    steps = []
    for index, raw_step in enumerate(raw_steps):
        context = f"steps[{index}]"
        if (
            not isinstance(raw_step, dict)
            or set(raw_step)
            != {
                "id",
                "description",
                "type",
                "script",
                "arguments",
                "check_arguments",
            }
            or raw_step["type"] != "python"
            or not isinstance(raw_step["id"], str)
            or not raw_step["id"]
            or not isinstance(raw_step["description"], str)
            or not raw_step["description"]
        ):
            raise ValueError(f"{context}: malformed Python step")
        check_value = raw_step["check_arguments"]
        steps.append(
            Step(
                raw_step["id"],
                raw_step["description"],
                _relative_path(raw_step["script"], f"{context}.script"),
                _strings(raw_step["arguments"], f"{context}.arguments"),
                None
                if check_value is None
                else _strings(check_value, f"{context}.check_arguments"),
            )
        )
    step_ids = tuple(step.id for step in steps)
    if len({value.casefold() for value in step_ids}) != len(step_ids):
        raise ValueError(f"{path}: duplicate step id")

    raw_profiles = document["profiles"]
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ValueError(f"{path}: profiles must be a nonempty object")
    discs = load_catalog()
    profiles = {}
    for name, raw_profile in raw_profiles.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(raw_profile, dict)
            or set(raw_profile) != {"description", "steps", "outputs"}
            or not isinstance(raw_profile["description"], str)
            or not raw_profile["description"]
        ):
            raise ValueError(f"{path}: malformed profile {name!r}")
        profile_steps = _strings(raw_profile["steps"], f"profiles.{name}.steps")
        profile_outputs = _strings(
            raw_profile["outputs"], f"profiles.{name}.outputs"
        )
        if len(set(profile_steps)) != len(profile_steps):
            raise ValueError(f"profiles.{name}: duplicate step")
        if unknown := [value for value in profile_steps if value not in step_ids]:
            raise ValueError(f"profiles.{name}: unknown steps {unknown}")
        if not profile_outputs or any(value not in discs for value in profile_outputs):
            raise ValueError(f"profiles.{name}: invalid disc outputs")
        profiles[name] = Profile(
            name,
            raw_profile["description"],
            profile_steps,
            profile_outputs,
        )
    if "default" not in profiles or profiles["default"].steps != step_ids:
        raise ValueError(f"{path}: default profile must execute every step in order")
    return BuildConfig(
        tuple(steps),
        profiles,
        {name: disc.output_path for name, disc in discs.items()},
    )


def _command(step: Step, *, check: bool) -> list[str] | None:
    arguments = step.check_arguments if check else step.arguments
    if arguments is None:
        return None
    return [sys.executable, "-B", str(PSP_ROOT / step.script), *arguments]


def print_plan(config: BuildConfig, profile: Profile, *, check: bool) -> None:
    by_id = {step.id: step for step in config.steps}
    print(f"Profile: {profile.name} - {profile.description}")
    print(f"Mode: {'check' if check else 'build'}")
    for index, step_id in enumerate(profile.steps, 1):
        command = _command(by_id[step_id], check=check)
        action = "skip" if command is None else " ".join(command)
        print(f"{index}. {step_id}: {action}")
    print("Outputs:")
    for disc_id in profile.outputs:
        print(f"  [{disc_id}] {config.disc_outputs[disc_id]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="?", default="default")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--list-steps", action="store_true")
    parser.add_argument("--list-profiles", action="store_true")
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
        if arguments.profile not in config.profiles:
            parser.error(f"unknown profile: {arguments.profile}")
        profile = config.profiles[arguments.profile]
        if arguments.plan:
            print_plan(config, profile, check=arguments.check)
            return
        by_id = {step.id: step for step in config.steps}
        for step_id in profile.steps:
            step = by_id[step_id]
            print(f"\n== {step.id}: {step.description} ==", flush=True)
            command = _command(step, check=arguments.check)
            if command is None:
                print("skipped (write-only setup step)")
                continue
            result = subprocess.run(command, cwd=PSP_ROOT, check=False)
            if result.returncode:
                raise SystemExit(result.returncode)
        for disc_id in profile.outputs:
            output = config.disc_outputs[disc_id]
            if not output.is_file():
                raise ValueError(f"PSP build output is missing: {output}")
        action = "verified" if arguments.check else "built"
        print(f"\nPSP images {action}:")
        for disc_id in profile.outputs:
            print(f"  [{disc_id}] {config.disc_outputs[disc_id]}")
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

