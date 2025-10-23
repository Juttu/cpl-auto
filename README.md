# CPL(Career Portal Links) monitor

A tiny wrapper that runs job-scraping scripts **in series** and stores results in text files.
---

## Setup

### 1) Create & activate a virtual environment

**macOS / Linux (bash/zsh)**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Install requirements
```bash
pip install -r requirements.txt
```

### 3) Configure environment variables

>1. This step only needed - If the values expire
>2. These are open websites(NO LOGIN NEEDED) - General understanding is they **"DO NOT EXPIRE"** 
>3. If you see `401/403`, open DevTools and copy fresh values into `.env`.

---

## Run

**Run both scripts (no limits):**
```bash
python main.py
```

**Run with limits (examples):**
```bash
python main.py --kla=20 --cvs=15
python main.py --kla=50
python main.py --cvs=10
```

Execution is **serial**: KLA → CVS.

---

## Outputs

- **KLA results:** `kla/kla-auto.txt`  
- **CVS Health results:** `cvs-health/cvs-health-auto.txt`

Each file is **overwritten** on every run.

---

## Next Steps(probably): 
1. Add more career portals (KLA(Done), CVS HEALTH(Done).....etccccc)
2. Make the function in main.py run every {x} minutes
3. Filter jobs(right now it just gets **ALL** the **MOST RECENT** jobs)
4. Add some kind of notification system

---

## Extra Info


- **KLA** → `kla/kla-auto.py` → outputs `kla/kla-auto.txt`  
  - Direct usage:
    ```bash
    python kla/kla-auto.py
    python kla/kla-auto.py --4
    ```

- **CVS Health** → `cvs-health/cvs-health-auto.py` → outputs `cvs-health/cvs-health-auto.txt`  
  - Direct usage:
    ```bash
    python cvs-health/cvs-health-auto.py
    python cvs-health/cvs-health-auto.py --4
    ```


