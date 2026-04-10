import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Recommendation:
    patch_path: str
    status: str
    reasons: List[str]
    suggested_commands: List[str]


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _patch_header_paths(patch_path: str) -> List[str]:
    txt = _read_text(patch_path)
    out = []
    for line in txt.splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            if p.startswith("b/"):
                p = p[2:]
            if p != "/dev/null":
                out.append(p)
    return out


def _strip_candidates_from_header_paths(header_paths: List[str]) -> List[int]:
    anchors = {"ecoaims_frontend", "ecoaims_backend", "docs", "scripts", "api", "dashboard"}
    candidates = set()
    for p in header_paths:
        pp = str(p).lstrip("/")
        parts = [x for x in pp.split("/") if x]
        for i, seg in enumerate(parts):
            if seg in anchors:
                candidates.add(i)
        for i in range(len(parts)):
            cand = "/".join(parts[i:])
            if os.path.exists(cand):
                candidates.add(i)
                break
    return sorted(candidates)


def _looks_like_git_patch(patch_path: str) -> bool:
    txt = _read_text(patch_path)
    return "diff --git " in txt


def _list_reports(report_dir: str) -> List[str]:
    if not os.path.isdir(report_dir):
        return []
    out = []
    for name in os.listdir(report_dir):
        if name.endswith(".json"):
            out.append(os.path.join(report_dir, name))
    out.sort(key=lambda p: os.path.getmtime(p))
    return out


def _last_attempt_failure_class(report: Dict[str, Any]) -> str:
    attempts = report.get("attempts") or []
    if isinstance(attempts, list) and attempts:
        last = attempts[-1]
        if isinstance(last, dict):
            v = last.get("failure_class")
            if isinstance(v, str) and v:
                return v
    return "unknown"


def _pick_flags(report: Dict[str, Any]) -> Tuple[int, str, bool]:
    strip = int(report.get("git_apply_strip") or 1)
    ws = str(report.get("git_apply_whitespace") or "nowarn")
    reverse_applicable = bool(report.get("reverse_applicable") or False)
    return strip, ws, reverse_applicable


def _recommend(report: Dict[str, Any]) -> Recommendation:
    patch_path = str(report.get("patch_path") or "")
    ok = bool(report.get("ok") or False)
    strip, ws, reverse_applicable = _pick_flags(report)
    failure_class = _last_attempt_failure_class(report)
    touched = report.get("touched_files") or []
    changed = report.get("changed_files") or []

    if ok:
        return Recommendation(
            patch_path=patch_path,
            status="ok",
            reasons=["patch applied successfully"],
            suggested_commands=[],
        )

    reasons: List[str] = []
    cmds: List[str] = []
    base = "./ecoaims_frontend_env/bin/python scripts/apply_patch_with_retry.py"
    header_paths = []
    if isinstance(report.get("patch_header_paths_raw"), list):
        header_paths = [str(x) for x in report.get("patch_header_paths_raw") if isinstance(x, str)]
    if not header_paths and patch_path:
        header_paths = _patch_header_paths(patch_path)
    git_style = _looks_like_git_patch(patch_path) if patch_path else False
    three_way_hint = "--three-way auto"
    if not git_style:
        three_way_hint = "--three-way never"

    if reverse_applicable:
        reasons.append("reverse_applicable=true (indikasi patch sudah pernah diterapkan)")
        cmds.append(f'{base} --patch "{patch_path}" --dry-run --strip {strip} --whitespace {ws} {three_way_hint}')
        return Recommendation(patch_path=patch_path, status="already_applied_or_conflict", reasons=reasons, suggested_commands=cmds)

    if failure_class == "context_mismatch":
        reasons.append("failure_class=context_mismatch (konteks baris berbeda dari patch)")
        if ws != "fix":
            reasons.append("coba whitespace fix untuk mengurangi mismatch akibat formatter")
        cmds.append(f'{base} --patch "{patch_path}" --strip {strip} --whitespace fix {three_way_hint}')
        if strip != 0:
            cmds.append(f'{base} --patch "{patch_path}" --strip 0 --whitespace fix {three_way_hint}')
        if strip != 1:
            cmds.append(f'{base} --patch "{patch_path}" --strip 1 --whitespace fix {three_way_hint}')
        cmds.append(f'{base} --patch "{patch_path}" --strip {strip} --whitespace fix {three_way_hint} --allow-rejects')
    elif failure_class == "path_missing":
        reasons.append("failure_class=path_missing (file target tidak ditemukan; sering karena strip mismatch)")
        strip_suggestions = _strip_candidates_from_header_paths(header_paths) if header_paths else []
        preferred_strip = strip_suggestions[0] if strip_suggestions else 1
        reasons.append(f"strip_suggestions={strip_suggestions or ['(none)']} (dari header_paths_raw + file existence)")
        if strip != preferred_strip:
            reasons.append(f"prioritaskan --strip {preferred_strip} untuk mencoba match path")
        cmds.append(f'{base} --patch "{patch_path}" --strip {preferred_strip} --whitespace {ws} {three_way_hint}')
        if preferred_strip != 0:
            cmds.append(f'{base} --patch "{patch_path}" --strip 0 --whitespace {ws} {three_way_hint}')
        if preferred_strip != 1:
            cmds.append(f'{base} --patch "{patch_path}" --strip 1 --whitespace {ws} {three_way_hint}')
        cmds.append(f'{base} --patch "{patch_path}" --strip {preferred_strip} --whitespace fix {three_way_hint}')
    elif failure_class == "corrupt_patch":
        reasons.append("failure_class=corrupt_patch (patch rusak/tidak valid)")
        cmds.append("regenerate patch dari baseline terbaru (pastikan unified diff lengkap)")
    elif failure_class == "patch_not_found":
        reasons.append("failure_class=patch_not_found (path patch tidak ditemukan)")
        cmds.append("pastikan path patch benar dan dapat diakses oleh runner")
    else:
        reasons.append(f"failure_class={failure_class}")
        cmds.append(f'{base} --patch "{patch_path}" --strip {strip} --whitespace fix {three_way_hint}')
        cmds.append(f'{base} --patch "{patch_path}" --strip 0 --whitespace fix {three_way_hint}')
        cmds.append(f'{base} --patch "{patch_path}" --strip {strip} --whitespace fix {three_way_hint} --allow-rejects')

    if isinstance(touched, list) and not touched:
        reasons.append("touched_files kosong (indikasi mismatch path parsing); coba --strip 0")

    if isinstance(changed, list) and len(changed) == 0:
        reasons.append("changed_files kosong (patch tidak mengubah file) — bisa karena mismatch atau patch sudah applied")

    return Recommendation(patch_path=patch_path, status="failed", reasons=reasons, suggested_commands=cmds)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="output/patch_validation", help="Direktori report JSON patch validation")
    ap.add_argument("--n", type=int, default=3, help="Jumlah report terbaru")
    ap.add_argument("--only-failed", action="store_true", help="Ambil hanya report dengan ok=false")
    ap.add_argument("--format", default="md", choices=["md", "json"])
    args = ap.parse_args()

    report_dir = os.path.abspath(str(args.dir))
    reports = _list_reports(report_dir)
    if not reports:
        if args.format == "json":
            print(json.dumps({"error": "no_reports_found", "dir": report_dir}, sort_keys=True))
        else:
            print(f"Tidak ada report patch validation ditemukan di: {report_dir}")
            print("Buat report dengan menjalankan:")
            print("  ./ecoaims_frontend_env/bin/python scripts/apply_patch_with_retry.py --patch /path/to/change.diff")
        return 2

    loaded: List[Dict[str, Any]] = []
    for p in reports:
        try:
            loaded.append(_load_json(p))
        except Exception:
            continue

    if args.only_failed:
        loaded = [r for r in loaded if not bool(r.get("ok") or False)]

    loaded = loaded[-max(1, int(args.n)) :]
    recs = [_recommend(r) for r in loaded]

    if args.format == "json":
        out = []
        for r in recs:
            out.append({"patch_path": r.patch_path, "status": r.status, "reasons": r.reasons, "suggested_commands": r.suggested_commands})
        print(json.dumps({"dir": report_dir, "recommendations": out}, sort_keys=True, indent=2))
        return 0

    print(f"Patch playbook (latest {len(recs)}) from {report_dir}")
    for i, r in enumerate(recs, start=1):
        print("")
        print(f"{i}. patch={r.patch_path} status={r.status}")
        for reason in r.reasons:
            print(f"   - {reason}")
        for cmd in r.suggested_commands:
            print(f"   - {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
