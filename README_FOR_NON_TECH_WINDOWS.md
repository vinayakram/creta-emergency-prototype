# Creta Emergency Assistant — Prototype v1
## Step-by-step Windows guide (for non‑technical users)

This guide is written so you can run the prototype **without needing to know programming**.

---

# What you will get at the end
A small website on your computer where you can type a situation like:

- “My battery is dead. How do I jump‑start?”
- “Engine overheating, what should I do?”
- “Flat tire, how do I change the wheel?”

…and it will show:
- **Steps**
- **Warnings / Cautions**
- **Required tools**
- **Sources** (pages/excerpts from the manual)

---

# Part A — Install the two required apps (one time only)

## 1) Install Python 3.13
You said you already have Python 3.13.9 — good.

To verify:
1. Press **Win** key
2. Type: `cmd` → open **Command Prompt**
3. Run:
   ```bat
   py -V
   ```
If you see something like `Python 3.13.x`, you’re good.

## 2) Install Node.js (for the website)
You need **Node.js 18+** (LTS is best).

To verify after installing:
```bat
node -v
npm -v
```

---

# Part B — Download the Hyundai manual PDF (required)

1. Open your browser.
2. Copy and paste this link to download the PDF:

```text
https://www.hyundai.com/content/dam/hyundai/in/en/data/connect-to-service/owners-manual/2025/creta&cretanline-Jan2024-Present.pdf
```

3. Save it as:
```
creta_manual.pdf
```

4. Move it into this folder inside the project:
```
backend\data\
```

So the final path is:
```
backend\data\creta_manual.pdf
```

---

# Part C — Run the prototype (5 simple steps)

> Tip: When you double‑click the scripts below, **a black window** will open and show progress.
> Do not close it until it says it is finished.

## Step 1 — Backend install (one time)
Double‑click:
```
01_SETUP_BACKEND.bat
```

Wait until it ends with something like “DONE”.

## Step 2 — Index the manual (one time, takes a few minutes)
Double‑click:
```
02_INGEST_MANUAL.bat
```

This “reads the PDF and builds the search index”.

✅ When finished, it prints: “Ingested … chunks …”

## Step 3 — Start the backend (must stay open)
Double‑click:
```
03_START_BACKEND.bat
```

You should see:
- `Uvicorn running on http://127.0.0.1:8000`

**Leave this window open.**

## Step 4 — Frontend install (one time)
Double‑click:
```
04_SETUP_FRONTEND.bat
```

Wait until it finishes.

## Step 5 — Start the website (must stay open)
Double‑click:
```
05_START_WEBSITE.bat
```

It will show a local link like:
- `http://localhost:5173`

Open that link in your browser.

---

# Troubleshooting

## If Step 2 says “PDF not found”
Make sure the file exists exactly at:
```
backend\data\creta_manual.pdf
```

## If scripts close immediately
Right‑click the `.bat` file → choose “Run as administrator” (or run from Command Prompt).

## If `py` is not recognized
Your Python install is missing the Python Launcher.
Reinstall Python and enable “Install launcher for all users”.

## If the website starts but results show an error
That usually means:
- You did not run Step 2 (ingestion), or
- The backend window (Step 3) is closed

---

# Safety notice
This is a prototype for quick information retrieval. In real emergencies, prioritize safety and follow local laws.
If you are in immediate danger, contact emergency services / roadside assistance.
