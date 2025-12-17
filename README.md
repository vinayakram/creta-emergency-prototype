# Creta Emergency Assistant — Prototype v1

A **manual-grounded emergency guidance assistant** for the Hyundai Creta owner’s manual.

This prototype helps users quickly find **safe, structured, and traceable instructions** during vehicle-related emergency situations — without relying on generic chatbots.

---

## What this project does

After setup, you will have a **local website** running on your computer where you can type questions like:

- “My battery is dead. How do I jump-start?”
- “Engine overheating — what should I do?”
- “Flat tire — how do I change the wheel?”

For each question, the assistant returns:

- ✅ **Step-by-step instructions**
- ⚠️ **Warnings / cautions / notices**
- 🛠 **Required tools**
- 📖 **Sources** (exact excerpts from the owner’s manual)

All answers are **grounded in the official Hyundai Creta owner’s manual**.  
This is **not** a generic AI chatbot.

---

## Why this approach

Vehicle emergencies require **accuracy and safety**.

This system:
- Searches only the owner’s manual
- Avoids mixing unrelated procedures
- Produces **structured output**, not free-form text
- Shows sources so answers can be verified

This makes it suitable for **technical demos, internal reviews, and proof-of-concepts**.

---

## High-level flow (no technical knowledge needed)

1. You type a question in the browser
2. The backend searches the manual using semantic search
3. Relevant manual sections are retrieved
4. The system extracts:
   - steps
   - warnings
   - tools
5. A structured response is sent back to the website

---

## What you need before starting (one-time)

### Windows PC
Windows 10 or Windows 11

### Python 3.13
Verify:
```
py -V
```

### Node.js (18+)
Verify:
```
node -v
npm -v
```

---

## Download the Hyundai Creta owner’s manual (required)

Download:
```
https://www.hyundai.com/content/dam/hyundai/in/en/data/connect-to-service/owners-manual/2025/creta&cretanline-Jan2024-Present.pdf
```

Rename to:
```
creta_manual.pdf
```

Move to:
```
backend\data\creta_manual.pdf
```

---

## Run the prototype (5 steps)

### Step 1 — Backend setup
```
01_SETUP_BACKEND.bat
```

### Step 2 — Ingest manual
```
02_INGEST_MANUAL.bat
```

### Step 3 — Start backend (keep open)
```
03_START_BACKEND.bat
```

### Step 4 — Frontend setup
```
04_SETUP_FRONTEND.bat
```

### Step 5 — Start website
```
05_START_WEBSITE.bat
```

Open:
```
http://localhost:5173
```

---

## Troubleshooting

- **PDF not found** → Check `backend\data\creta_manual.pdf`
- **Backend errors** → Ensure ingestion ran and backend is open
- **py not found** → Reinstall Python with launcher enabled

---

## Intended use

- Technical demos
- Proof-of-concepts
- Internal evaluations
- Technical sales walkthroughs

Not intended for production.

---

## Safety notice

This is an information prototype only.  
In real emergencies, prioritize safety and contact roadside assistance or emergency services.

---

## Project status

**Prototype v1**
- Local-only
- Manual-grounded retrieval
- Structured output (steps, warnings, tools, sources)
- Includes evaluation scripts
