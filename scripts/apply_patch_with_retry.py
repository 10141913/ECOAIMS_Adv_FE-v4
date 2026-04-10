import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str], *, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _touched_files_from_numstat(patch_path: str, *, strip: int) -> list[str]:
    p = _run(["git", "apply", f"-p{int(strip)}", "--numstat", patch_path])
    files = []
    for line in (p.stdout or "").splitlines():
        parts = [x for x in line.split("\t") if x]
        if len(parts) >= 3:
            files.append(parts[2])
    return sorted(set(files))


def _touched_files_from_patch_bytes(patch_bytes: bytes, *, strip: int) -> list[str]:
    files = set()
    for raw in patch_bytes.splitlines():
        line = raw.decode(errors="ignore")
        if line.startswith("+++ "):
            p = line[4:].strip()
            if p.startswith("b/"):
                p = p[2:]
            if p == "/dev/null":
                continue
            parts = p.split("/")
            if int(strip) > 0 and len(parts) > int(strip):
                p = "/".join(parts[int(strip) :])
            files.add(p)
    return sorted(files)


def _clamp_sleep(base_s: float, max_s: float, n: int) -> float:
    return min(float(max_s), float(base_s) * (2.0**int(n)))


def _classify_git_apply_failure(stderr: str) -> str:
    s = (stderr or "").lower()
    if "patch failed" in s or "does not apply" in s:
        return "context_mismatch"
    if "corrupt patch" in s or "patch fragment without header" in s:
        return "corrupt_patch"
    if "does not exist in index" in s:
        return "index_missing_for_3way"
    if "does not exist in working tree" in s:
        return "path_missing"
    if "no such file or directory" in s:
        return "path_missing"
    if "can't open patch" in s:
        return "patch_not_found"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", required=True, help="Path ke patch file (unified diff)")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--backoff-base-s", type=float, default=0.5)
    ap.add_argument("--backoff-max-s", type=float, default=8.0)
    ap.add_argument("--strip", type=int, default=1, help="Path strip untuk git apply -pN (default 1 untuk patch a/ b/)")
    ap.add_argument("--whitespace", default="nowarn", choices=["nowarn", "warn", "error", "error-all", "fix"], help="Behavior whitespace untuk git apply")
    ap.add_argument("--three-way", default="auto", choices=["auto", "always", "never"], help="Gunakan --3way (auto=aktif jika patch bergaya git)")
    ap.add_argument("--allow-rejects", action="store_true", help="Jika tetap gagal, coba apply dengan --reject (menghasilkan *.rej)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    patch_path = os.path.abspath(args.patch)
    with open(patch_path, "rb") as f:
        patch_bytes = f.read()
    patch_sha256 = _sha256_bytes(patch_bytes)

    patch_text = patch_bytes.decode(errors="ignore")
    looks_like_git_patch = "diff --git " in patch_text
    header_paths_raw = _touched_files_from_patch_bytes(patch_bytes, strip=0)
    if str(args.three_way) == "always":
        use_3way = True
    elif str(args.three_way) == "never":
        use_3way = False
    else:
        use_3way = bool(looks_like_git_patch)

    strip = int(args.strip)
    files = _touched_files_from_numstat(patch_path, strip=strip)
    if not files:
        files = _touched_files_from_patch_bytes(patch_bytes, strip=strip)
    before: Dict[str, str] = {}
    for fp in files:
        if os.path.exists(fp) and os.path.isfile(fp):
            before[fp] = _sha256_file(fp)

    attempt_logs = []
    ok = False
    reverse_applicable = False
    for i in range(max(1, int(args.retries))):
        base_cmd = ["git", "apply", f"-p{strip}", "--check", f"--whitespace={args.whitespace}"]
        rev_cmd = ["git", "apply", f"-p{strip}", "--reverse", "--check", f"--whitespace={args.whitespace}"]
        if use_3way:
            base_cmd.insert(3, "--3way")
            rev_cmd.insert(4, "--3way")
        chk = _run(base_cmd + [patch_path])
        rev = _run(rev_cmd + [patch_path])
        reverse_applicable = reverse_applicable or (rev.returncode == 0)
        attempt_logs.append(
            {
                "attempt": i + 1,
                "three_way": bool(use_3way),
                "check_exit_code": chk.returncode,
                "check_stdout": (chk.stdout or "")[:5000],
                "check_stderr": (chk.stderr or "")[:5000],
                "reverse_check_exit_code": rev.returncode,
                "reverse_check_stdout": (rev.stdout or "")[:2000],
                "reverse_check_stderr": (rev.stderr or "")[:2000],
                "failure_class": _classify_git_apply_failure(chk.stderr or ""),
            }
        )
        if chk.returncode == 0:
            if args.dry_run:
                ok = True
                break
            apply_cmd = ["git", "apply", f"-p{strip}", f"--whitespace={args.whitespace}"]
            if use_3way:
                apply_cmd.append("--3way")
            aply = _run(apply_cmd + [patch_path])
            attempt_logs[-1].update(
                {
                    "apply_exit_code": aply.returncode,
                    "apply_stdout": (aply.stdout or "")[:5000],
                    "apply_stderr": (aply.stderr or "")[:5000],
                }
            )
            if aply.returncode == 0:
                ok = True
                break
        time.sleep(_clamp_sleep(float(args.backoff_base_s), float(args.backoff_max_s), i))

    if not ok and not args.dry_run and args.allow_rejects:
        rej_cmd = ["git", "apply", f"-p{strip}", "--reject", f"--whitespace={args.whitespace}"]
        if use_3way:
            rej_cmd.append("--3way")
        rej = _run(rej_cmd + [patch_path])
        attempt_logs.append(
            {
                "attempt": "reject_apply",
                "three_way": bool(use_3way),
                "apply_exit_code": rej.returncode,
                "apply_stdout": (rej.stdout or "")[:5000],
                "apply_stderr": (rej.stderr or "")[:5000],
                "failure_class": _classify_git_apply_failure(rej.stderr or ""),
            }
        )
        if rej.returncode == 0:
            ok = True

    after: Dict[str, str] = {}
    for fp in files:
        if os.path.exists(fp) and os.path.isfile(fp):
            after[fp] = _sha256_file(fp)

    changed_files = sorted([fp for fp in files if before.get(fp) != after.get(fp)])
    unchanged_files = sorted([fp for fp in files if fp in before and fp in after and before.get(fp) == after.get(fp)])

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_dir = os.path.join(os.getcwd(), "output", "patch_validation")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"{ts}_patch_validation.json")
    report = {
        "ok": bool(ok),
        "dry_run": bool(args.dry_run),
        "patch_path": patch_path,
        "patch_sha256": patch_sha256,
        "patch_looks_like_git_patch": bool(looks_like_git_patch),
        "patch_header_paths_raw": header_paths_raw,
        "git_apply_strip": strip,
        "git_apply_whitespace": str(args.whitespace),
        "git_apply_three_way": str(args.three_way),
        "git_apply_three_way_enabled": bool(use_3way),
        "reverse_applicable": bool(reverse_applicable),
        "touched_files": files,
        "changed_files": changed_files,
        "unchanged_files": unchanged_files,
        "before_sha256": before,
        "after_sha256": after,
        "attempts": attempt_logs,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print(f"ok={str(ok).lower()} report={report_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
