#!/usr/bin/env python3
import argparse, json, sys, re
from pathlib import Path

def norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def job_key(job: dict) -> str:
    # Prefer job_link if present; else fall back to normalized title+location+date
    link = (job.get("job_link") or "").strip()
    if link:
        return f"link::{link}"
    title = norm(job.get("job_title"))
    loc   = norm(job.get("job_location"))
    date  = norm(job.get("job_posted_date"))
    return f"tld::{title}|{loc}|{date}"

def load_jobs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON array")
    return data

def compare(a_path: Path, b_path: Path, show_examples=10):
    A = load_jobs(a_path)
    B = load_jobs(b_path)

    a_keys = [job_key(j) for j in A]
    b_keys = [job_key(j) for j in B]

    setA, setB = set(a_keys), set(b_keys)

    onlyA = sorted(setA - setB)
    onlyB = sorted(setB - setA)
    inter = setA & setB

    print(f"File A: {a_path}  (jobs: {len(A)})")
    print(f"File B: {b_path}  (jobs: {len(B)})")
    print(f"Intersection: {len(inter)}")
    print(f"Only in A: {len(onlyA)}")
    print(f"Only in B: {len(onlyB)}")

    if onlyA or onlyB:
        print("\n== Differences ==")
        if onlyA:
            print(f"-- Only in A (showing up to {show_examples}):")
            for k in onlyA[:show_examples]:
                print("  ", k)
        if onlyB:
            print(f"-- Only in B (showing up to {show_examples}):")
            for k in onlyB[:show_examples]:
                print("  ", k)
        return 2  # sets differ
    else:
        # Sets equal — check order
        if a_keys == b_keys:
            print("\nSets match and order matches ✅")
            return 0
        else:
            print("\nSets match but order differs ⚠️")
            # Show first few index mismatches
            mismatches = []
            for i, (ka, kb) in enumerate(zip(a_keys, b_keys)):
                if ka != kb:
                    mismatches.append((i, ka, kb))
                if len(mismatches) >= show_examples:
                    break
            if mismatches:
                print(f"First {len(mismatches)} order mismatches:")
                for i, ka, kb in mismatches:
                    print(f"  idx {i}:")
                    print(f"    A: {ka}")
                    print(f"    B: {kb}")
            return 1  # only order differs

def main():
    ap = argparse.ArgumentParser(
        description="Compare two CVS jobs JSON files (ignoring order by default)."
    )
    ap.add_argument("file_a", nargs="?", default="cvs-test.json")
    ap.add_argument("file_b", nargs="?", default="cvs-test-temp.json")
    ap.add_argument("--show", type=int, default=10, help="max examples to print")
    args = ap.parse_args()

    a_path = Path(args.file_a)
    b_path = Path(args.file_b)
    if not a_path.exists() or not b_path.exists():
        print("Input file not found.", file=sys.stderr)
        sys.exit(3)

    rc = compare(a_path, b_path, show_examples=args.show)
    sys.exit(rc)

if __name__ == "__main__":
    main()
