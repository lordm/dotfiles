"""The hook merges in scripts/setup-tts.sh.

These are the step that makes anything speak: without them a fresh machine
gets a working daemon, a working `tts say`, and zero narration, with no error
to explain it. The script exposes its merge helpers when sourced with
TTS_SETUP_LIB=1, so each case here runs the real functions against a scratch
HOME. The live ~/.claude/settings.json and ~/.codex/config.toml are never
touched by any of it.
"""

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SETUP = REPO / "scripts" / "setup-tts.sh"
CLAUDE_HOOK = "python3 ~/workspace/dotfiles/tts/hooks/claude.py"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("bash") is None,
    reason="the merge is implemented in bash + jq",
)


def merge(home: Path, *functions: str) -> str:
    """Run merge helpers from setup-tts.sh against a scratch HOME."""
    script = f'TTS_SETUP_LIB=1 source "{SETUP}"\n' + "\n".join(functions or
                                                              ("merge_claude_hooks",
                                                               "merge_codex_hooks"))
    proc = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def settings(home: Path) -> dict:
    return json.loads((home / ".claude/settings.json").read_text())


def commands(home: Path, event: str) -> list[str]:
    groups = settings(home).get("hooks", {}).get(event, [])
    return [hook["command"] for group in groups for hook in group.get("hooks", [])]


def codex(home: Path) -> dict:
    return tomllib.loads((home / ".codex/config.toml").read_text())


def test_fresh_machine_gets_both_harnesses_wired(tmp_path):
    merge(tmp_path)

    assert commands(tmp_path, "Stop") == [CLAUDE_HOOK]
    assert commands(tmp_path, "Notification") == [CLAUDE_HOOK]
    hooks = codex(tmp_path)["hooks"]
    assert len(hooks["Stop"]) == 1
    assert len(hooks["PermissionRequest"]) == 1
    assert "codex.py" in hooks["Stop"][0]["hooks"][0]["command"]


def test_rerunning_does_not_duplicate_anything(tmp_path):
    """Re-running the installer is the normal case, not an edge case.

    An earlier version of this merge deduplicated one array and not the other
    and grew a second Notification hook on every run, so every notification
    was spoken twice.
    """
    merge(tmp_path)
    first_json = (tmp_path / ".claude/settings.json").read_text()
    first_toml = (tmp_path / ".codex/config.toml").read_text()

    output = merge(tmp_path)

    assert (tmp_path / ".claude/settings.json").read_text() == first_json
    assert (tmp_path / ".codex/config.toml").read_text() == first_toml
    assert commands(tmp_path, "Notification") == [CLAUDE_HOOK]
    assert "already has the TTS hooks" in output


def test_hooks_the_user_already_had_survive(tmp_path):
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".codex").mkdir(parents=True)
    (tmp_path / ".claude/settings.json").write_text(json.dumps({
        "model": "opus",
        "hooks": {
            "Notification": [{"matcher": "", "hooks": [
                {"type": "command", "command": "notify-send 'needs input'"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "my-audit-hook"}]}],
        },
    }))
    (tmp_path / ".codex/config.toml").write_text(
        'model = "gpt-5"\n\n[[hooks.Stop]]\n[[hooks.Stop.hooks]]\n'
        'type = "command"\ncommand = "my-own-stop-hook"\n'
    )

    merge(tmp_path)

    assert settings(tmp_path)["model"] == "opus"
    assert commands(tmp_path, "PreToolUse") == ["my-audit-hook"]
    assert commands(tmp_path, "Notification") == ["notify-send 'needs input'", CLAUDE_HOOK]
    assert codex(tmp_path)["model"] == "gpt-5"
    assert len(codex(tmp_path)["hooks"]["Stop"]) == 2


def test_an_existing_file_is_backed_up_before_it_changes(tmp_path):
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".codex").mkdir(parents=True)
    (tmp_path / ".claude/settings.json").write_text('{"model": "opus"}')
    (tmp_path / ".codex/config.toml").write_text('model = "gpt-5"\n')

    merge(tmp_path)

    backups = list((tmp_path / ".claude").glob("settings.json.bak-*"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == {"model": "opus"}
    assert [p.read_text() for p in (tmp_path / ".codex").glob("config.toml.bak-*")] \
        == ['model = "gpt-5"\n']


def test_unreadable_settings_json_is_left_exactly_as_found(tmp_path):
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude/settings.json").write_text("{ not json at all")

    output = merge(tmp_path, "merge_claude_hooks")

    assert (tmp_path / ".claude/settings.json").read_text() == "{ not json at all"
    assert "SKIPPED" in output


def test_a_config_toml_that_would_not_parse_is_left_alone(tmp_path):
    """`[hooks.Stop]` as a plain table collides with the fragment's `[[hooks.Stop]]`.

    The merged file is parsed before it is allowed to land, so the collision
    costs the user their narration, not their Codex config.
    """
    (tmp_path / ".codex").mkdir(parents=True)
    original = '[hooks.Stop]\nnot = "an array of tables"\n'
    (tmp_path / ".codex/config.toml").write_text(original)

    output = merge(tmp_path, "merge_codex_hooks")

    assert (tmp_path / ".codex/config.toml").read_text() == original
    assert "SKIPPED" in output


def test_a_stale_marked_block_is_replaced_not_repeated(tmp_path):
    (tmp_path / ".codex").mkdir(parents=True)
    (tmp_path / ".codex/config.toml").write_text(
        'model = "x"\n\n# >>> agent-tts >>>\n[[hooks.Stop]]\n[[hooks.Stop.hooks]]\n'
        'type = "command"\ncommand = "moved-since/codex.py"\n# <<< agent-tts <<<\n'
    )

    merge(tmp_path, "merge_codex_hooks")

    text = (tmp_path / ".codex/config.toml").read_text()
    assert text.count("# >>> agent-tts >>>") == 1
    assert "moved-since" not in text
    assert "tts/hooks/codex.py" in text
    assert codex(tmp_path)["model"] == "x"


def test_the_settings_file_keeps_its_mode_across_the_merge(tmp_path):
    """A merge must not relax the permissions of the file it edits.

    ~/.claude/settings.json is deliberately 600 and holds an `env` block. The
    merge writes a temp and `mv`s it over the original, and `mv` replaces the
    inode -- so without care the original's mode is discarded and the temp's
    umask mode is what survives, silently publishing the file to the group and
    the world on a default 002 umask. Our own installer is the last place that
    should be doing that.
    """
    (tmp_path / ".claude").mkdir(parents=True)
    settings_file = tmp_path / ".claude/settings.json"
    settings_file.write_text(json.dumps({"env": {"SOME_TOKEN": "pretend-secret"}}))
    settings_file.chmod(0o600)

    merge(tmp_path, "umask 0002", "merge_claude_hooks")

    assert CLAUDE_HOOK in commands(tmp_path, "Stop"), "the merge did not run"
    assert settings_file.stat().st_mode & 0o777 == 0o600
    assert settings(tmp_path)["env"]["SOME_TOKEN"] == "pretend-secret"


def test_a_settings_file_created_by_the_merge_is_private(tmp_path):
    """On a fresh machine the mode comes from the umask unless we set it."""
    merge(tmp_path, "umask 0002", "merge_claude_hooks")

    settings_file = tmp_path / ".claude/settings.json"
    assert CLAUDE_HOOK in commands(tmp_path, "Stop"), "the merge did not run"
    assert settings_file.stat().st_mode & 0o777 == 0o600
