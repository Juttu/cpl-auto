# main.py
import sys
import subprocess
from pathlib import Path

def run_many(times=10):
    root = Path(__file__).parent
    script = root / "cvs-test" / "cvs-test.py"     # <-- points to ./cvs-test/cvs-test.py
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")

    for i in range(times):
        print(f"\n===== i={i} =====")
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(script.parent),           # run inside cvs-test/
                text=True,
                capture_output=True,
                check=True,
            )
            # print exactly what cvs-test.py printed
            print(proc.stdout.strip())
        except subprocess.CalledProcessError as e:
            print(f"❌ Error i={i}: {e.stderr.strip() or e.stdout.strip()}")

if __name__ == "__main__":
    run_many(10)
