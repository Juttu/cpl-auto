# main.py
import os
import sys
import subprocess
from pathlib import Path


try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).parent.resolve()

def load_env():
    """Load .env from the folder where main.py lives (if python-dotenv is installed)."""
    if load_dotenv:
        load_dotenv(dotenv_path=ROOT / ".env")

def parse_limits(argv):
    """
    Optional flags:
      --kla=N   → passes `--N` to kla/kla-auto.py
      --cvs=N   → passes `--N` to cvs-health/cvs-health-auto.py
    No flags → run both with no extra args.
    """
    kla_args, cvs_args = [], []
    for a in argv:
        if a.startswith("--kla="):
            n = a.split("=", 1)[1]
            if n.isdigit():
                kla_args = [f"--{n}"]
        elif a.startswith("--cvs="):
            n = a.split("=", 1)[1]
            if n.isdigit():
                cvs_args = [f"--{n}"]
    return kla_args, cvs_args

def run_script(script_rel_path: str, args=None):
    """
    Run a Python script in its own directory so its outputs land beside it.
    Blocks until completion (serial execution).
    """
    script_path = ROOT / script_rel_path
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    env = os.environ.copy()
    print(f"\n=== Running: {' '.join(cmd)} (cwd={script_path.parent}) ===")
    # Inherit stdout/stderr so you see live output
    result = subprocess.run(cmd, cwd=str(script_path.parent), env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

def main():
    load_env()
    kla_args, cvs_args = parse_limits(sys.argv[1:])

    # 1) Run KLA
    run_script("kla/kla-auto.py", kla_args)

    # 2) Run CVS-Health
    run_script("cvs-health/cvs-health-auto.py", cvs_args)

    print("\nAll done ✅")

if __name__ == "__main__":
    main()
