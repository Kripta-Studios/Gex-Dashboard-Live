"""Bounded operational fixtures, no models, labels, outcomes or market child."""

from pathlib import Path
import json
import sys
import time
from types import SimpleNamespace

import pytest

import launch_monthly_test_20261023 as launcher


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return dict(path=str(path), sha256=launcher.sha(path))


def free(value=2_000_000_000):
    return dict(available_ram_bytes=value, free_commit_bytes=value, utc=launcher.utc())


@pytest.fixture
def environment(tmp_path, monkeypatch):
    real_code = launcher.CODE
    code = tmp_path / "code"
    code.mkdir()
    expectations = launcher.overlay.review_expectations()
    names = set(expectations["files"]) | set(expectations["original_dependencies"])
    names |= set(launcher.NEW_FILES) | {
        launcher.REVIEW.name,
        launcher.SCIENTIFIC_REVIEW.name,
    }
    for name in names:
        (code / name).write_text("synthetic published member " + name)
    for name, value in (
        ("CODE", code),
        ("REPO", tmp_path),
        ("WRAPPER", code / launcher.WRAPPER.name),
        ("REVIEW", code / launcher.REVIEW.name),
        ("SCIENTIFIC_REVIEW", code / launcher.SCIENTIFIC_REVIEW.name),
    ):
        monkeypatch.setattr(launcher, name, value)
    monkeypatch.setattr(launcher, "WRAPPER_SHA", launcher.sha(launcher.WRAPPER))
    monkeypatch.setattr(launcher, "REVIEW_SHA", launcher.sha(launcher.REVIEW))
    monkeypatch.setattr(launcher, "SCRIPT", code / launcher.NEW_FILES[0])
    monkeypatch.setattr(launcher.overlay, "HERE", code)
    monkeypatch.setattr(launcher.overlay, "SCIENTIFIC_ROOT", tmp_path / "science")
    monkeypatch.setattr(launcher.overlay, "ROOT", tmp_path / "science_parent")
    monkeypatch.setattr(launcher, "resources", free)
    monkeypatch.setattr(
        launcher.overlay.shared.psutil, "pid_exists", lambda _pid: False
    )
    old = tmp_path / "validation"
    old.mkdir()
    old_runtime = old / "runtime"
    old_runtime.mkdir()
    command = [
        sys.executable,
        "-u",
        str(code / "run_monthly_resource_overlay.py"),
        "--runtime-root",
        str(old_runtime),
    ]
    process = put(
        old / "process_binding.json",
        dict(pid=12345, creation_time=100.0, command=command),
    )
    opened = put(
        old / "monitor_open.json",
        dict(
            status="PROCESS_HANDLE_RETAINED",
            pid=12345,
            creation_time=100.0,
            command=command,
            monitor_started_utc="2026-10-23T09:00:00+00:00",
            process_receipt_sha256=process["sha256"],
        ),
    )
    monitor = old / "monitor.py"
    monitor.write_text("synthetic monitor authority")
    opened_record = launcher.read(opened["path"])
    opened_record["monitor_code_sha256"] = launcher.sha(monitor)
    opened = put(Path(opened["path"]), opened_record)
    exited = put(
        old / "monitored_exit.json",
        dict(
            status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE",
            pid=12345,
            creation_time=100.0,
            exit_code=0,
            observed_utc="2026-10-23T10:00:00+00:00",
            process_receipt_sha256=process["sha256"],
        ),
    )
    launch = put(
        old_runtime / "launch.json",
        dict(
            status="MONTHLY_RESOURCE_OVERLAY_STARTED",
            pid=12345,
            original_argv=[*launcher.overlay.original_argv()[:-1], "validation"],
        ),
    )
    audit = put(old / "audit.json", {"synthetic_audit_boundary": True})
    launcher_review = put(
        code / launcher.LAUNCH_REVIEW_NAME,
        dict(
            status="PASS_MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW",
            decision="CLEAR",
            scope="IMPLEMENTATION_ONLY",
            runtime_authorized=False,
            files={name: launcher.sha(code / name) for name in launcher.NEW_FILES},
        ),
    )
    runtime = dict(
        status=launcher.overlay.RUNTIME_STATUS,
        allowed_read_roots=[str(tmp_path), str(real_code)],
        validation=dict(
            runtime_root=str(old_runtime),
            audit=audit,
            process_binding=process,
            monitor_open=opened,
            monitored_exit=exited,
            monitor_code=dict(path=str(monitor), sha256=launcher.sha(monitor)),
            runtime_launch=launch,
        ),
        launch_binding=dict(
            status="REVIEWED_MONTHLY_TEST_ONE_SHOT_LAUNCH",
            runtime_root=str(tmp_path / "runtime_new"),
            logs_root=str(tmp_path / "logs_new"),
            published_files=launcher.publication_files(Path(launcher_review["path"])),
            launcher_review=launcher_review,
        ),
    )
    runtime_path = code / "MONTHLY_TEST_LAUNCH_RUNTIME_FIXTURE.json"
    put(runtime_path, runtime)
    admitted_calls, git_calls = [], []

    def admit(*args):
        admitted_calls.append(args)
        return dict(
            authorities=SimpleNamespace(files={audit["path"]: audit["sha256"]}),
            preserved={},
            freeze=dict(selected_mode=None),
        )

    monkeypatch.setattr(launcher.overlay, "admit", admit)

    def git(args, **_kwargs):
        git_calls.append(args)
        assert args[:2] == ["git", "show"]
        return SimpleNamespace(
            stdout=(tmp_path / args[2].split(":", 1)[1]).read_bytes()
        )

    monkeypatch.setattr(launcher.subprocess, "run", git)
    return SimpleNamespace(
        path=runtime_path,
        runtime=runtime,
        audit_sha=audit["sha256"],
        calls=admitted_calls,
        git_calls=git_calls,
        real_code=real_code,
    )


def preflight(env):
    return launcher.preflight(env.path, launcher.sha(env.path), env.audit_sha, "a" * 40)


def test_exact_publication_and_null_selection_admitted_without_outputs(environment):
    receipt = preflight(environment)
    assert receipt["selected_mode"] is None and not receipt["executed"]
    assert receipt["validation_exit_code"] == 0 and receipt["validation_pid"] == 12345
    assert len(environment.calls) == 1 and environment.git_calls
    assert (
        not Path(receipt["runtime_root"]).exists()
        and not Path(receipt["logs_root"]).exists()
    )
    assert receipt["command"] == launcher.command(
        Path(receipt["runtime_root"]), environment.path, environment.audit_sha
    )
    assert "--stage" not in receipt["command"]


@pytest.mark.parametrize(
    "fault",
    [
        "runtime_sha",
        "audit_sha",
        "publication",
        "code",
        "roots",
        "runtime_exists",
        "logs_exists",
        "pid_live",
        "exit_nonzero",
    ],
)
def test_preflight_rejects_without_scientific_child(environment, monkeypatch, fault):
    env = environment
    review_sha, audit_sha = launcher.sha(env.path), env.audit_sha
    if fault == "runtime_sha":
        review_sha = "0" * 64
    elif fault == "audit_sha":
        audit_sha = "0" * 64
    elif fault == "publication":
        monkeypatch.setattr(
            launcher.subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(stdout=b"changed"),
        )
    elif fault == "code":
        env.runtime["launch_binding"]["published_files"][launcher.NEW_FILES[0]] = (
            "0" * 64
        )
    elif fault == "roots":
        env.runtime["launch_binding"]["logs_root"] = env.runtime["launch_binding"][
            "runtime_root"
        ]
    elif fault == "runtime_exists":
        Path(env.runtime["launch_binding"]["runtime_root"]).mkdir()
    elif fault == "logs_exists":
        Path(env.runtime["launch_binding"]["logs_root"]).mkdir()
    elif fault == "pid_live":
        monkeypatch.setattr(
            launcher.overlay.shared.psutil, "pid_exists", lambda _pid: True
        )
    else:
        item = env.runtime["validation"]["monitored_exit"]
        record = launcher.read(item["path"])
        record["exit_code"] = 7
        env.runtime["validation"]["monitored_exit"] = put(Path(item["path"]), record)
    if fault in ("code", "roots", "exit_nonzero"):
        put(env.path, env.runtime)
        review_sha = launcher.sha(env.path)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        lambda *_a, **_k: pytest.fail("Scientific child before admission"),
    )
    with pytest.raises(ValueError):
        launcher.preflight(env.path, review_sha, audit_sha, "a" * 40)


def test_default_check_cli_cannot_spawn(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launcher",
            "--runtime-review",
            str(tmp_path / "review"),
            "--runtime-review-sha256",
            "a" * 64,
            "--expected-validation-audit-sha256",
            "b" * 64,
            "--publication-commit",
            "c" * 40,
        ],
    )
    monkeypatch.setattr(launcher, "preflight", lambda *_a: dict(status="CHECK_ONLY"))
    monkeypatch.setattr(launcher, "launch", lambda *_a: pytest.fail("Default launched"))
    assert launcher.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "CHECK_ONLY"


def test_resource_boundaries():
    launcher.gate(free())
    for field in ("available_ram_bytes", "free_commit_bytes"):
        value = free()
        value[field] -= 1
        with pytest.raises(ValueError, match="2GB"):
            launcher.gate(value)


def fake_child(environment, monkeypatch, exit_code, *, interrupt=False):
    calls, waits = [], []
    child = SimpleNamespace(pid=22222, returncode=None)

    def drain():
        waits.append(1)
        child.returncode = exit_code
        return exit_code

    child.wait = drain

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        root = Path(environment.runtime["launch_binding"]["runtime_root"])
        put(
            root / "launch.json",
            dict(
                status="MONTHLY_TEST_RESOURCE_OVERLAY_STARTED",
                pid=child.pid,
                original_argv=launcher.overlay.original_argv(),
                original_run_contract_sha256=launcher.overlay.RUN_CONTRACT_SHA,
                scientific_inputs_changed=False,
                review=dict(
                    scope="test",
                    original_dependencies=launcher.overlay.monthly.dependency_hashes(),
                ),
            ),
        )
        return child

    class Retained:
        def __init__(self, actual):
            assert actual is child
            self.child = actual

        def creation_time(self):
            return 123.5

        def wait_exit(self):
            waits.append(1)
            if interrupt and len(waits) == 1:
                raise KeyboardInterrupt
            child.returncode = exit_code
            return exit_code

    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    monkeypatch.setattr(launcher, "RetainedProcess", Retained)
    return calls, waits


@pytest.mark.parametrize("exit_code", [0, 7])
def test_retained_receipts_pass_existing_chain_verifier(
    environment, monkeypatch, exit_code
):
    receipt = preflight(environment)
    calls, waits = fake_child(environment, monkeypatch, exit_code)
    assert launcher.launch(receipt) == exit_code
    assert len(calls) == len(waits) == 1
    logs = Path(receipt["logs_root"])
    chain = launcher.read(logs / "process_chain.json")
    assert chain["status"] == "PROCESS_CHAIN_RECORDED"
    authority = launcher.overlay.Authorities(
        (logs, Path(receipt["runtime_root"]), environment.real_code, launcher.CODE)
    )
    _, exited = launcher.overlay.verify_process_chain(
        chain["members"], authority, Path(receipt["runtime_root"]), validation=False
    )
    assert (
        exited["exit_code"] == exit_code
        and exited["scientific_completion_certified"] is False
    )
    assert exited["exit_code_source"] == "GetExitCodeProcess_retained_Popen_handle"
    assert "source_launch" not in chain["members"]


def test_resource_drop_immediately_before_popen_has_no_child(environment, monkeypatch):
    receipt = preflight(environment)
    monkeypatch.setattr(launcher, "resources", lambda: free(1_999_999_999))
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        lambda *_a, **_k: pytest.fail("Low resources child"),
    )
    with pytest.raises(ValueError, match="2GB"):
        launcher.launch(receipt)
    logs = Path(receipt["logs_root"])
    assert (logs / "preflight.json").exists() and not (
        logs / "process_binding.json"
    ).exists()


def test_interrupt_keeps_retained_handle_until_actual_exit(environment, monkeypatch):
    receipt = preflight(environment)
    calls, waits = fake_child(environment, monkeypatch, 7, interrupt=True)
    assert launcher.launch(receipt) == 7
    assert len(calls) == 1 and len(waits) == 2
    assert len(list(Path(receipt["logs_root"]).glob("interruption_*.json"))) == 1


def test_observer_write_failure_still_waits_and_does_not_retry(
    environment, monkeypatch
):
    receipt = preflight(environment)
    calls, waits = fake_child(environment, monkeypatch, 7)
    publish = launcher.publish

    def fail_binding(root, name, value):
        if name == "process_binding.json":
            raise OSError("synthetic receipt storage error")
        return publish(root, name, value)

    monkeypatch.setattr(launcher, "publish", fail_binding)
    with pytest.raises(OSError, match="storage"):
        launcher.launch(receipt)
    logs = Path(receipt["logs_root"])
    assert len(calls) == len(waits) == 1 and (logs / "monitor_failure.json").exists()
    assert not (logs / "monitored_exit.json").exists()


def test_native_monitor_initialization_failure_drains_original_child(
    environment, monkeypatch
):
    receipt = preflight(environment)
    calls, waits = fake_child(environment, monkeypatch, 7)

    def broken(_child):
        raise OSError("synthetic Win32 monitor setup failure")

    monkeypatch.setattr(launcher, "RetainedProcess", broken)
    with pytest.raises(OSError, match="setup"):
        launcher.launch(receipt)
    assert len(calls) == len(waits) == 1
    assert not (Path(receipt["logs_root"]) / "monitored_exit.json").exists()


def test_failed_interruption_log_does_not_abandon_handle(environment, monkeypatch):
    receipt = preflight(environment)
    calls, waits = fake_child(environment, monkeypatch, 7, interrupt=True)
    original = launcher.publish

    def failing(root, name, value):
        if name.startswith("interruption_"):
            raise OSError("synthetic interrupted log storage failure")
        return original(root, name, value)

    monkeypatch.setattr(launcher, "publish", failing)
    assert launcher.launch(receipt) == 7
    assert len(calls) == 1 and len(waits) == 2
    assert (Path(receipt["logs_root"]) / "monitored_exit.json").exists()


@pytest.mark.parametrize("when", ["opening", "closing"])
def test_monitor_code_mutation_cannot_reseal_wrong_bytes(
    environment, monkeypatch, when
):
    receipt = preflight(environment)
    calls, waits = fake_child(environment, monkeypatch, 7)
    original = launcher.RetainedProcess

    class Changed(original):
        def __init__(self, child):
            super().__init__(child)
            if when == "opening":
                launcher.SCRIPT.write_bytes(b"changed after Popen")

        def wait_exit(self):
            code = super().wait_exit()
            if when == "closing":
                launcher.SCRIPT.write_bytes(b"changed during observation")
            return code

    monkeypatch.setattr(launcher, "RetainedProcess", Changed)
    with pytest.raises(ValueError, match="Pinned file changed"):
        launcher.launch(receipt)
    assert len(calls) == len(waits) == 1
    logs = Path(receipt["logs_root"])
    assert not (logs / "process_chain.json").exists()
    if when == "closing":
        assert (
            launcher.read(logs / "monitor_open.json")["monitor_code_sha256"]
            == receipt["publication_files"][str(launcher.SCRIPT)]
        )


def test_equivalent_root_separators_pass_check_and_execute(environment, monkeypatch):
    for field in ("runtime_root", "logs_root"):
        environment.runtime["launch_binding"][field] = Path(
            environment.runtime["launch_binding"][field]
        ).as_posix()
    put(environment.path, environment.runtime)
    receipt = preflight(environment)
    calls, _ = fake_child(environment, monkeypatch, 0)
    assert launcher.launch(receipt) == 0 and len(calls) == 1


@pytest.mark.parametrize("fault", ["hash", "decision", "files"])
def test_launcher_review_is_independently_pinned(environment, fault):
    item = environment.runtime["launch_binding"]["launcher_review"]
    if fault == "hash":
        item["sha256"] = "0" * 64
    else:
        value = launcher.read(item["path"])
        if fault == "decision":
            value["decision"] = "NOT_REVIEWED"
        else:
            value["files"][launcher.NEW_FILES[0]] = "0" * 64
        replacement = put(Path(item["path"]), value)
        environment.runtime["launch_binding"]["launcher_review"] = replacement
        environment.runtime["launch_binding"]["published_files"][
            Path(item["path"]).name
        ] = replacement["sha256"]
    put(environment.path, environment.runtime)
    with pytest.raises(ValueError):
        preflight(environment)


@pytest.mark.parametrize("exit_code", [0, 7, 259])
def test_native_fast_python_handle_creation_and_actual_exit(exit_code):
    if sys.platform != "win32":
        pytest.skip("Windows retained handle fixture")
    started = time.time()
    child = launcher.subprocess.Popen(
        [sys.executable, "-c", f"raise SystemExit({exit_code})"],
        creationflags=launcher.subprocess.CREATE_NO_WINDOW,
    )
    assert child.wait(timeout=10) == exit_code
    retained = launcher.RetainedProcess(child)
    created = retained.creation_time()
    assert started - 1 <= created <= time.time() + 1
    assert retained.wait_exit() == exit_code  # 259 is valid after a signalled handle.
    assert retained.creation_time() == created


def test_frozen_wrapper_and_review_bytes_intact():
    assert (
        launcher.sha(Path(launcher.overlay.__file__))
        == "f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1"
    )
    assert (
        launcher.sha(
            Path(launcher.overlay.__file__).with_name(
                "MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json"
            )
        )
        == "49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280"
    )
