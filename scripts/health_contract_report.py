#!/usr/bin/env python3
import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _short(s: Optional[str], n: int = 12) -> str:
    if not s:
        return "-"
    t = str(s)
    return t if len(t) <= n else t[:n] + "…"


def _load_jsonl(path: str, last_n: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except FileNotFoundError:
        return []
    if last_n > 0 and len(rows) > last_n:
        return rows[-last_n:]
    return rows


def _get(d: Dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _frontend_pid(row: Dict[str, Any]) -> Optional[int]:
    pid = _get(row, "meta", "frontend_runtime", "pid")
    try:
        return int(pid)
    except Exception:
        return None


def _frontend_started_at(row: Dict[str, Any]) -> str:
    v = _get(row, "meta", "frontend_runtime", "started_at")
    return str(v) if v is not None else ""


def _backend_err_class(row: Dict[str, Any]) -> Optional[str]:
    errs = _get(row, "meta", "errors")
    if not isinstance(errs, list):
        return None
    for e in errs:
        if not isinstance(e, dict):
            continue
        if e.get("scope") == "backend":
            err = e.get("error")
            if isinstance(err, str) and err:
                return err
    return None


@dataclass(frozen=True)
class Event:
    ts: int
    kind: str
    detail: str


def _extract_events(rows: List[Dict[str, Any]]) -> Tuple[List[Event], Optional[int], Optional[Tuple[int, int]]]:
    events: List[Event] = []
    last_backend_change_ts: Optional[int] = None
    last_backend_change_fe_pid: Optional[int] = None
    fe_restart_after_change: Optional[Tuple[int, int]] = None

    last_pid: Optional[int] = None
    last_started_at = ""

    for r in rows:
        ts = int(r.get("ts") or 0)
        errc = _backend_err_class(r)
        if errc in {"backend_connection_refused", "backend_timeout"}:
            events.append(Event(ts=ts, kind="backend_down", detail=errc))

        changed = _get(r, "diff", "changed")
        if isinstance(changed, list) and changed:
            if "contract_manifest_hash" in changed or "registry_manifest_hash" in changed:
                last_backend_change_ts = ts
                last_backend_change_fe_pid = _frontend_pid(r)
                events.append(
                    Event(
                        ts=ts,
                        kind="backend_contract_changed",
                        detail=f"contract_manifest_hash={_short(_get(r,'startup_info','contract_manifest_hash'))} registry_manifest_hash={_short(_get(r,'contracts_index','registry_manifest_hash'))}",
                    )
                )
            if "endpoint_map_hash" in changed or "endpoint_map_count" in changed:
                last_backend_change_ts = last_backend_change_ts or ts
                last_backend_change_fe_pid = last_backend_change_fe_pid or _frontend_pid(r)
                events.append(
                    Event(
                        ts=ts,
                        kind="backend_registry_changed",
                        detail=f"endpoint_map_count={_get(r,'contracts_index','endpoint_map_count')} endpoint_map_hash={_short(_get(r,'contracts_index','endpoint_map_hash'))}",
                    )
                )

        pid = _frontend_pid(r)
        started_at = _frontend_started_at(r)
        if pid and (last_pid is None or pid != last_pid or (started_at and started_at != last_started_at)):
            events.append(Event(ts=ts, kind="frontend_restart", detail=f"pid={pid} started_at={started_at or '-'}"))
            last_pid = pid
            last_started_at = started_at
            if last_backend_change_ts and last_backend_change_fe_pid and fe_restart_after_change is None:
                if pid != last_backend_change_fe_pid and ts >= last_backend_change_ts:
                    fe_restart_after_change = (last_backend_change_ts, ts)

    return events, last_backend_change_ts, fe_restart_after_change


def _fmt_ts(ts: int) -> str:
    try:
        import datetime as _dt

        return _dt.datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")
    except Exception:
        return str(ts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.getenv("ECOAIMS_HEALTH_CONTRACT_OUT", ".run/health_contract.jsonl"))
    ap.add_argument("--last-n", type=int, default=400)
    ap.add_argument("--events", type=int, default=18)
    args = ap.parse_args()

    rows = _load_jsonl(args.path, last_n=int(args.last_n))
    if not rows:
        print(f"Tidak ada data. Jalankan dulu: make health-contract-start (file={args.path})")
        return 2

    last = rows[-1]
    events, last_backend_change_ts, fe_restart_after_change = _extract_events(rows)
    events_tail = events[-int(args.events) :] if int(args.events) > 0 else events

    print("Health Contract Report")
    print(f"- file={args.path}")
    print(f"- last_ts={_fmt_ts(int(last.get('ts') or 0))}")
    print(f"- fe_url={last.get('fe_url')}")
    print(f"- backend_url={last.get('backend_url')}")
    print(f"- backend_health_ok={bool(last.get('backend_health_ok'))}")
    print(f"- startup.schema_version={_get(last,'startup_info','schema_version') or '-'} contract_version={_get(last,'startup_info','contract_version') or '-'}")
    print(
        "- manifest_hash(startup/index)=%s / %s"
        % (
            _short(_get(last, "startup_info", "contract_manifest_hash"), 16),
            _short(_get(last, "contracts_index", "registry_manifest_hash"), 16),
        )
    )
    print(
        "- endpoint_map=%s hash=%s"
        % (
            _get(last, "contracts_index", "endpoint_map_count"),
            _short(_get(last, "contracts_index", "endpoint_map_hash"), 16),
        )
    )

    if last_backend_change_ts:
        print(f"- last_backend_change={_fmt_ts(int(last_backend_change_ts))}")
        if fe_restart_after_change:
            a, b = fe_restart_after_change
            print(f"- frontend_restart_after_backend_change=yes backend_change={_fmt_ts(a)} frontend_restart={_fmt_ts(b)}")
        else:
            print("- frontend_restart_after_backend_change=no (jika muncul mismatch di UI, jalankan make doctor-stack atau restart FE)")

    if events_tail:
        print("\nRecent Events")
        for e in events_tail:
            print(f"- { _fmt_ts(e.ts) } {e.kind} {e.detail}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
