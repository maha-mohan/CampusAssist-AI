"""Run the golden question set against a running API and report accuracy.

Usage:
    python eval/run_eval.py --api http://localhost:8000/api [--csv eval/golden_set.csv]

A question PASSES when:
  - should_answer=yes: the bot answered AND the answer contains expected_contains
  - should_answer=no : the bot declined (answered=false) — i.e. it did not guess
Add 150+ real questions from students (English, Tamil, Tanglish) before go-live.
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def post(url: str, payload: dict) -> dict:
    """POST JSON; waits and retries when the API's rate limiter answers 429.
    (Tip: run the API with RATE_LIMIT_PER_MINUTE=1000 while evaluating.)"""
    for attempt in range(8):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(10)
    raise RuntimeError("Rate limited repeatedly; raise RATE_LIMIT_PER_MINUTE for evals")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000/api")
    ap.add_argument("--csv", default=str(Path(__file__).with_name("golden_set.csv")))
    ap.add_argument("--min-accuracy", type=float, default=0.85)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    passed, latencies, failures = 0, [], []
    for row in rows:
        sid = post(f"{args.api}/chat/session", {})["session_id"]  # fresh session: no history leakage
        t0 = time.perf_counter()
        d = post(f"{args.api}/chat/message", {"session_id": sid, "message": row["question"]})
        latencies.append(time.perf_counter() - t0)
        if row["should_answer"] == "yes":
            ok = d["answered"] and row["expected_contains"].lower() in d["answer"].lower()
        else:
            ok = not d["answered"]
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {row['question']}")
        if not ok:
            failures.append((row, d["answer"][:200]))

    acc = passed / len(rows)
    latencies.sort()
    print("\n" + "=" * 60)
    print(f"Accuracy: {passed}/{len(rows)} = {acc:.0%}  (target {args.min_accuracy:.0%})")
    print(f"Latency p50: {latencies[len(latencies)//2]:.2f}s   p95: {latencies[int(len(latencies)*0.95)-1]:.2f}s")
    for row, ans in failures:
        print(f"\n✗ {row['question']}\n  expected: {row['expected_contains'] or '(decline)'}\n  got: {ans}")
    return 0 if acc >= args.min_accuracy else 1


if __name__ == "__main__":
    sys.exit(main())
