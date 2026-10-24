"""Retain a validated Windows process handle and record its real exit status."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import psutil

ROOT = Path(__file__).resolve().parent
receipt = json.loads((ROOT / "process_monitor_binding.json").read_text(encoding="utf-8"))
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
kernel.GetProcessTimes.restype = wintypes.BOOL
kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel.GetExitCodeProcess.restype = wintypes.BOOL
kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel.WaitForSingleObject.restype = wintypes.DWORD
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL


def publish(name, value):
    path = ROOT / name
    temporary = path.with_suffix(path.suffix + ".partial")
    if path.exists() or temporary.exists():
        raise FileExistsError("Preserve monitor receipt: " + str(path))
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def utc():
    return datetime.now(timezone.utc).isoformat()


handle = kernel.OpenProcess(0x00100000 | 0x1000, False, receipt["pid"])
if not handle:
    raise ctypes.WinError(ctypes.get_last_error())
try:
    creation, exit_time, system, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in (creation, exit_time, system, user))):
        raise ctypes.WinError(ctypes.get_last_error())
    creation_unix = ((creation.dwHighDateTime << 32) | creation.dwLowDateTime) / 10_000_000 - 11644473600
    if abs(creation_unix - receipt["creation_time"]) > 0.001:
        raise RuntimeError("PID reused: creation time differs")
    process = psutil.Process(receipt["pid"])
    if process.cmdline() != receipt["command"]:
        raise RuntimeError("Live command differs from launch receipt")
    opened = dict(status="PROCESS_HANDLE_RETAINED", pid=receipt["pid"], creation_time=creation_unix,
                  monitor_pid=os.getpid(), monitor_started_utc=utc(), access_mask=0x00100000 | 0x1000,
                  process_receipt_sha256=hashlib.sha256((ROOT / "process_monitor_binding.json").read_bytes()).hexdigest(),
                  monitor_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  command=receipt["command"])
    publish("monitor_open.json", opened)
    print(json.dumps(opened), flush=True)
    started = time.monotonic()
    peak_rss = peak_private = sampled = 0
    next_report = 0
    with (ROOT / "monitor_observations.jsonl").open("x", encoding="utf-8") as stream:
        while True:
            wait = kernel.WaitForSingleObject(handle, 0)
            if wait == 0:
                break
            if wait != 258:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                memory = process.memory_info()
                peak_rss = max(peak_rss, memory.rss, getattr(memory, "peak_wset", 0))
                peak_private = max(peak_private, getattr(memory, "private", 0))
                sampled += 1
                if time.monotonic() >= next_report:
                    observation = dict(status="RUNNING", utc=utc(), pid=receipt["pid"],
                                       elapsed_since_attach_s=time.monotonic() - started,
                                       rss_bytes=memory.rss, private_bytes=getattr(memory, "private", 0),
                                       cpu_s=sum(process.cpu_times()[:2]),
                                       system_available_ram_bytes=psutil.virtual_memory().available,
                                       stderr_bytes=(ROOT / "stderr.log").stat().st_size,
                                       stdout_bytes=(ROOT / "stdout.log").stat().st_size)
                    stream.write(json.dumps(observation) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                    print(json.dumps(observation), flush=True)
                    next_report = time.monotonic() + 45
            except psutil.NoSuchProcess:
                pass
            time.sleep(1)
    code = wintypes.DWORD()
    if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
        raise ctypes.WinError(ctypes.get_last_error())
    result = dict(status="PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE", pid=receipt["pid"],
                  creation_time=creation_unix, exit_code=int(code.value), observed_utc=utc(),
                  wall_seconds_since_launch=time.time() - receipt["started_unix"],
                  monitored_seconds=time.monotonic() - started, memory_samples=sampled,
                  sampling_seconds=1, peak_rss_bytes=peak_rss, peak_private_bytes=peak_private,
                  peaks_scope="RSS includes Windows peak_wset; private peak sampled after attach",
                  process_receipt_sha256=opened["process_receipt_sha256"])
    publish("monitored_exit.json", result)
    print(json.dumps(result), flush=True)
finally:
    kernel.CloseHandle(handle)
