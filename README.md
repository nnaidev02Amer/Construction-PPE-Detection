<div align="center">

<a href="Visuals/ppe-detection-demo.mp4">
  <img src="Visuals/demo-video.webp" alt="Construction PPE Detection demo video" width="100%" />
</a>

<sub>▶ <a href="Visuals/ppe-detection-demo.mp4">Watch the demo video</a> (promotional clip from the original project)</sub>

# 🦺 Construction PPE Detection – PPE Safety Monitor
### AI-based construction-site safety monitoring with YOLO, OpenCV, FastAPI and a web dashboard

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![YOLO](https://img.shields.io/badge/YOLOv8n-Ultralytics-orange)](https://github.com/ultralytics/ultralytics)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*Academic prototype – final-year engineering project. Not a certified industrial safety system.*

</div>

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Features](#2-features)
3. [System architecture](#3-system-architecture)
4. [Project folder structure](#4-project-folder-structure)
5. [System requirements](#5-system-requirements)
6. [Installation (Windows)](#6-installation-windows)
7. [Environment configuration](#7-environment-configuration)
8. [Model configuration](#8-model-configuration)
9. [Running the application](#9-running-the-application)
10. [User operating guide](#10-user-operating-guide)
11. [Camera setup](#11-camera-setup)
12. [Violation detection workflow](#12-violation-detection-workflow)
13. [Email notifications](#13-email-notifications)
14. [API documentation](#14-api-documentation)
15. [Database](#15-database)
16. [Testing](#16-testing)
17. [Troubleshooting](#17-troubleshooting)
18. [Security and limitations](#18-security-and-limitations)
19. [Screenshots](#19-screenshots)
20. [Future enhancements](#20-future-enhancements)
21. [License and credits](#21-license-and-credits)

---

## 1. Project overview

**Title:** Construction PPE Detection (dashboard name: *PPE Safety Monitor*).

**Introduction.** The application watches a camera feed (laptop webcam, IP camera or video file), finds construction workers in each frame and checks whether each one is wearing a **hard hat (helmet)** and a **high-visibility safety vest**. Violations are stored with an evidence screenshot, shown on a web dashboard in real time, summarised in daily and monthly reports and, optionally, emailed.

**Problem statement.** Construction sites are hazardous, and checking PPE (personal protective equipment) by eye is tiring, inconsistent and cannot cover every worker all the time. Missed violations are only noticed after an incident.

**Proposed solution.** A computer-vision pipeline runs on an ordinary laptop. A YOLO object-detection model finds people, hard hats and vests; a tracker gives each person a number; simple rules decide who is missing what and for how long; the result is saved and displayed.

**Objectives**
- Detect missing helmets and missing vests from a live camera.
- Record each violation once, with the worker's tracking ID, camera, time, confidence and a screenshot.
- Alert supervisors on the dashboard immediately, and by email if configured.
- Provide worker-wise history and daily/monthly safety reports from real stored data.
- Stay lightweight: SQLite database, CPU-capable, no cloud services required.

**Real-world applications (intended use cases):** site-entrance or work-zone monitoring, safety audits from recorded video, toolbox-talk statistics. This project demonstrates the concept; it has not been evaluated on a real site.

**How AI and computer vision are used**

| Step | Technique | Where in the code |
|---|---|---|
| Capture frames | OpenCV `VideoCapture` | `app/camera/*_source.py` |
| Find people, hard hats, vests | YOLOv8n object detector (`Model/ppe.pt`) | `app/core/detector.py` |
| (Optional) locate head and torso | YOLO pose model (`yolo11n-pose.pt`), keypoints for nose/eyes/ears and shoulders/hips | `app/core/pose.py` |
| Follow each worker across frames | IoU-based multi-object tracker | `app/core/tracker.py` |
| Decide who wears what | A hard hat must fall on the person's head region, a vest on the torso region; smoothed by a majority vote over recent frames | `app/core/ppe_assigner.py` |
| Decide when to record | Persistence timer + cooldown per worker and violation type | `app/core/violation_checker.py` |

**Technology stack:** Python, FastAPI + Uvicorn, Ultralytics YOLO on PyTorch, OpenCV, SQLAlchemy (async) with SQLite (`aiosqlite`), Pydantic settings, `aiosmtplib` for email, and a dashboard written in plain HTML, CSS and JavaScript (no external libraries or CDN).

---

## 2. Features

### Implemented

| # | Feature | Notes |
|---|---|---|
| 1 | **Helmet detection and violation recording** | Type `NO-Hardhat`. Red warning. |
| 2 | **Safety vest detection and violation recording** | Type `NO-Safety Vest`. Orange warning. |
| 3 | **Combined violation** | Type `COMBINED` (helmet **and** vest missing). Stored as **one** incident, not two. Magenta, thick border, "CRITICAL". |
| 4 | **Worker tracking and IDs** | Per camera session; not an identity (see [limitations](#18-security-and-limitations)). |
| 5 | **Violation screenshots** | Full-resolution frame with boxes, labels and a caption banner (violation, worker, time, camera). One image is shared by all incidents from the same frame. |
| 6 | **Real-time dashboard alerts** | **Server-Sent Events** (`GET /api/v1/events`): toast pop-up, bell counter, sidebar counter and live alert feed, no page refresh. |
| 7 | **Worker-wise history** | Workers page + `/workers` endpoints: total / helmet / vest / combined counts, last violation, full history. |
| 8 | **Daily report** | Workers detected, compliant workers, compliance %, violation counts, incidents per hour, per-camera table. |
| 9 | **Monthly report** | Totals, breakdown by type, daily trend, most frequent violation, per-camera table. |
| 10 | **CSV exports** | Violations (with the current filters), daily report, monthly report. |
| 11 | **PDF via browser print** | **Print / Save as PDF** button calls the browser's print dialog. There is no server-side PDF generation. |
| 12 | **Optional email notifications** | Per violation type, with screenshot attached, sent in the background. |
| 13 | **Camera configuration and webcam monitoring** | Webcam (device number), RTSP/IP camera URL, video file. Add, edit, delete, start, stop. |
| 14 | **Detection confidence settings** | General confidence and a separate Hardhat/Safety Vest confidence. |
| 15 | **Persistence and cooldown settings** | Editable on the Settings page, applied immediately. |
| 16 | **Dashboard overview and analytics** | Today's cards, 7-day trend chart, distribution chart, recent violations, camera status. |
| 17 | **No-signal handling** | If a camera stops delivering frames for 3 s it is shown as "No signal" and reconnection is attempted every 5 s. |

### Not implemented / limitations at a glance
- No login or user management.
- No face recognition and no permanent worker identity.
- No image or video *upload* for analysis (video files are used as a camera source by path).
- No server-generated PDF, no Slack integration (the `SLACK_WEBHOOK_URL` setting exists but no code uses it).
- Accuracy is limited by the trained model (see [Model configuration](#8-model-configuration)).
- The dashboard UI and real webcam use are verified manually only; see [Testing](#16-testing).

---

## 3. System architecture

```mermaid
flowchart TD
    A["Camera input<br/>webcam / RTSP / video file"] --> B["OpenCV frame capture<br/>app/camera/*_source.py"]
    B --> C["YOLO detector (Model/ppe.pt)<br/>app/core/detector.py"]
    B --> P["Pose model (optional)<br/>app/core/pose.py"]
    C --> D["PPE detection<br/>Person, Hardhat, Safety Vest boxes"]
    D --> E["Worker tracking<br/>app/core/tracker.py"]
    P --> F
    E --> F["Head/torso matching + smoothing<br/>app/core/ppe_assigner.py"]
    F --> G["Violation classification<br/>NO-Hardhat / NO-Safety Vest / COMBINED<br/>app/core/violation_checker.py"]
    G --> H["Screenshot capture<br/>app/core/screenshots.py"]
    H --> I[("SQLite database<br/>ppe_detection.db")]
    I --> J["FastAPI backend<br/>app/api/routes/"]
    J --> K["Frontend dashboard<br/>app/static/"]
    G --> L["Event bus (SSE)<br/>app/core/events.py"]
    L --> K
    G --> M["Email / webhook handlers<br/>app/alerts/ (background)"]
    I --> N["Reports and CSV export<br/>app/services/reports.py"]
    N --> J
```

**Roles of the main technologies**

| Technology | Role in this project |
|---|---|
| **OpenCV** | Opens webcam/RTSP/video sources, reads frames, draws boxes and labels, encodes JPEG for the live stream and screenshots |
| **YOLO (Ultralytics) / PyTorch** | Runs the PPE detector and the optional pose model |
| **FastAPI + Uvicorn** | REST API, MJPEG video stream, WebSocket (live counts), SSE (alerts), and serves the dashboard files |
| **SQLAlchemy + SQLite** | Stores cameras, violations, alert results, worker sightings and saved settings |
| **aiosmtplib** | Sends email without blocking detection |
| **HTML/CSS/JavaScript** | The six-page dashboard in `app/static/`; charts are drawn as inline SVG |

**Backend vs frontend.** There is a single server process. Starting `uvicorn` runs the backend (detection + API) *and* serves the dashboard files at `/`. You open the dashboard in a browser; the browser then calls the API at `/api/v1/...`.

---

## 4. Project folder structure

Only paths that exist in the repository (or are created at run time, marked ⚙) are listed.

```
Construction-PPE-Detection/
├── app/
│   ├── main.py                    # FastAPI app: start-up (DB, model, cameras), routers, static files
│   ├── alerts/                    # What happens after a violation
│   │   ├── base.py, dispatcher.py # Handler interface; runs handlers concurrently
│   │   ├── db_handler.py          # Saves the violation row (+ alert_log helper)
│   │   ├── email_handler.py       # SMTP email with screenshot; test-email helper
│   │   └── webhook_handler.py     # Optional JSON webhook
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/                # cameras, violations, workers, reports, app_settings, stream (video/WS/SSE), health
│   ├── camera/                    # manager.py (pipeline loop) + webcam/rtsp/file sources
│   ├── core/                      # config, detector, pose, tracker, ppe_assigner, violation_checker,
│   │                              # violation_types, screenshots, events, runtime_settings, frame_annotator, logging
│   ├── db/                        # models.py (tables), session.py (engine, auto-create, small migration)
│   ├── schemas/                   # Pydantic request/response models
│   ├── services/reports.py        # Daily/monthly statistics from the database
│   └── static/                    # index.html, app.js, style.css (the dashboard)
├── Model/ppe.pt                   # Trained YOLO weights (committed to git)
├── requirements/                  # base.txt, dev.txt, prod.txt
├── requirements.txt               # Legacy pins for the notebook / webcam.py (not needed for the app)
├── tests/                         # unit/ and integration/ (pytest) + conftest.py
├── test_assets/                   # sample.avi, sample.mp4 (see note below)
├── Visuals/                       # Banner images and demo video from the original project
├── docker/, docker-compose*.yml   # Optional Docker setup (PostgreSQL in the main compose file)
├── .github/workflows/             # ci.yml, build.yml
├── webcam.py                      # Original standalone script (no dashboard, no database)
├── ppe-detection.ipynb            # Training / experiment notebook
├── yolo_env.yml                   # Conda environment for the legacy script
├── pyproject.toml                 # Python >= 3.11, ruff and pytest settings
├── .env.example                   # Configuration template
├── ppe_detection.db        ⚙      # SQLite database (git-ignored)
├── violation_frames/       ⚙      # Screenshots (git-ignored)
├── yolo11n-pose.pt         ⚙      # Auto-downloaded pose weights
└── README.md
```

Notes
- There is **no `app/models/` folder**: the database models live in `app/db/models.py`.
- `alembic` is listed in `requirements/base.txt`, but no migration scripts exist and no code imports it. Database tables are created, and one column is added if missing, by `init_db()` in `app/db/session.py`.
- `test_assets/sample.mp4` is only a 258-byte placeholder and cannot be opened. `Visuals/ppe-detection-demo.mp4` (workers on a site) works as a test video source.

---

## 5. System requirements

| Item | Requirement |
|---|---|
| OS | Windows 10/11 (developed and run on Windows 11). The code itself is not Windows-specific. |
| Python | **3.11 or newer** (`pyproject.toml`: `requires-python = ">=3.11"`; CI and Docker use 3.11). **Recommended: 3.11.** The full automated suite and the application were also run successfully on Python 3.14.6 in the development environment. |
| Camera | Laptop webcam or any camera OpenCV can open (USB, RTSP/IP), or a video file |
| CPU / GPU | Runs on CPU (the development machine reports `torch.cuda.is_available() == False`). No device is set explicitly, so Ultralytics uses a CUDA GPU if PyTorch can see one. |
| RAM | Not measured; not specified by the project |
| Disk | Weights are small (`ppe.pt` ≈ 24.5 MB, pose model ≈ 6.3 MB). PyTorch and dependencies take several GB of pip downloads. Screenshots add disk use over time. Exact figures were not measured. |
| Internet | Needed to install packages, to download the pose weights once if `yolo11n-pose.pt` is missing, and for SMTP email. **The dashboard itself needs no internet** (no CDN). |

Real-time performance depends on your CPU, lighting, camera resolution and model inference speed. Detection and pose estimation run on every processed frame, so a slow CPU gives a low frame rate. See [Slow CPU](#17-troubleshooting) for ways to reduce load.

---

## 6. Installation (Windows)

```powershell
git clone https://github.com/Ansarimajid/Construction-PPE-Detection.git
cd Construction-PPE-Detection

py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
If `py -3.11` is not found, install Python 3.11 from python.org or use `py -3` (any 3.11+).

### Which requirements file?

| File | Contents | Use it for |
|---|---|---|
| `requirements/base.txt` | Everything the app needs to run | **Just running the dashboard** |
| `requirements/dev.txt` | `-r base.txt` + pytest, pytest-asyncio, pytest-cov, httpx, anyio, ruff | **Development and running the tests (recommended for examiners/developers)** |
| `requirements/prod.txt` | `-r base.txt` + gunicorn, asyncpg, psycopg2-binary | Docker / PostgreSQL deployment (`docker/Dockerfile` uses it; the Docker setup was not tested for this README) |
| `requirements.txt` (root) | Old fully pinned list (ultralytics 8.3.51, torch 2.5.1, matplotlib, ipython…) | Not needed. Only relevant to the original notebook / `webcam.py` |

```powershell
python -m pip install -r requirements/dev.txt     # development + tests
# or, to only run the app:
# python -m pip install -r requirements/base.txt
```

### Verify

```powershell
python --version
python -m pip list
python -m pip check
python -c "import fastapi, ultralytics, cv2, torch; print('imports OK')"
```

`pip check` should print `No broken requirements found.` (it did in the development environment).

### Packages (from `requirements/base.txt` and `dev.txt`)

The files only specify **minimum** versions (`>=`); pip installs the newest compatible ones. The "tested with" column shows what was installed when this README was verified – it is information, not a requirement.

| Package (minimum) | Tested with | Core? | Purpose / use in this project |
|---|---|---|---|
| fastapi ≥ 0.115 | 0.163.1 | Core | Web framework: API routes, WebSocket, SSE, static files |
| uvicorn[standard] ≥ 0.30 | 0.54.0 | Core | Server that runs `app.main:app` |
| pydantic ≥ 2.7 | 2.14.3 | Core | Request/response validation (`app/schemas`) |
| pydantic-settings ≥ 2.3 | 2.16.3 | Core | Reads `.env` into `app/core/config.py` |
| sqlalchemy[asyncio] ≥ 2.0 | 2.1.8 | Core | Database access and table definitions |
| aiosqlite ≥ 0.20 | 0.22.1 | Core | Async SQLite driver |
| ultralytics ≥ 8.3 | 8.4.215 | Core | Loads and runs the YOLO detection and pose models |
| torch ≥ 2.5.1 | 2.15.0 | Core | Deep-learning backend for YOLO |
| torchvision ≥ 0.20.1 | 0.29.2 | Core | Required by Ultralytics |
| opencv-python ≥ 4.11 | 5.0.0.93 | Core | Camera capture, drawing, JPEG encoding |
| numpy ≥ 1.26 | 2.5.5 | Core | Array maths for detections and tracking |
| aiosmtplib ≥ 3.0 | 5.1.3 | Core (email is optional) | Sends email |
| httpx ≥ 0.27 | 0.28.1 | Core | Webhook handler; also the test client |
| python-dotenv ≥ 1.0 | 1.2.4 | Supporting | Used by pydantic-settings to read `.env` |
| python-multipart ≥ 0.0.9 | 0.0.34 | Listed, not used | No current endpoint accepts form/file uploads |
| alembic ≥ 1.13 | 1.20.1 | Listed, not used | No migration scripts exist |
| pytest, pytest-asyncio, pytest-cov, anyio, ruff | pytest 9.2.0, pytest-asyncio 1.5.0 | Dev only | Test runner, async tests, coverage, linting |

---

## 7. Environment configuration

```powershell
Copy-Item .env.example .env
```

Run commands **from the project folder**: `.env`, `Model/ppe.pt` and the database path are relative to the current directory. Every variable is optional (defaults in `app/core/config.py`). Environment variables set in PowerShell override `.env`.

**Settings page overrides.** Values marked ✱ can also be changed on the dashboard's **Settings** page. Those are saved in the database table `app_settings` and **override `.env`** from then on.

| Variable | Default | Purpose | Example |
|---|---|---|---|
| `APP_ENV` | `dev` | `dev`, `staging` or `prod`. In `dev`, SQL statements are echoed to the console | `APP_ENV=dev` |
| `LOG_LEVEL` | `INFO` | Log detail | `LOG_LEVEL=DEBUG` |
| `HOST`, `PORT` | `0.0.0.0`, `8000` | Defined in settings but **not used** by the start command; use the `--host` / `--port` flags of uvicorn | – |
| `DATABASE_URL` | `sqlite+aiosqlite:///./ppe_detection.db` | Database location | `DATABASE_URL=sqlite+aiosqlite:///./ppe_detection.db` |
| `MODEL_PATH` | `Model/ppe.pt` | PPE detection weights | `MODEL_PATH=Model/ppe.pt` |
| `DETECTION_CONFIDENCE` ✱ | `0.5` | Minimum score for people and other objects | `0.5` |
| `PPE_ITEM_CONFIDENCE` ✱ | `0.3` | Minimum score for **Hardhat** and **Safety Vest** only | `0.3` |
| `ENABLE_TRACKING` | `true` | Worker IDs and per-worker violations. **If `false`, only the old whole-frame helmet check runs (no vest/combined violations).** | `true` |
| `TRACK_IOU_THRESHOLD` | `0.3` | Box overlap needed to treat two detections as the same worker | `0.3` |
| `TRACK_MAX_AGE` | `30` | Frames a lost worker keeps their ID | `30` |
| `TRACK_MIN_HITS` | `3` | Frames before a worker gets an ID | `3` |
| `PPE_SMOOTHING_WINDOW` | `15` | Majority vote over the last N frames (1 = off) | `15` |
| `ENABLE_POSE` | `true` | Use the pose model to find head/torso. `false` is lighter on CPU (boxes only) | `false` |
| `POSE_MODEL_PATH` | `yolo11n-pose.pt` | Pose weights (auto-downloaded if absent) | `yolo11n-pose.pt` |
| `POSE_CONFIDENCE` | `0.5` | Pose detection threshold | `0.5` |
| `VIOLATION_PERSIST_SECONDS` ✱ | `3` | How long a worker must stay non-compliant before an incident | `3` |
| `ALERT_COOLDOWN_SECONDS` ✱ | `10` in code (`.env.example` suggests `30`) | Minimum gap before the same worker + same violation type is recorded again | `30` |
| `FRAMES_DIR` | `violation_frames` | Screenshot folder | `violation_frames` |
| `EMAIL_ENABLED` ✱ | `true` | Master email switch (email still needs the fields below) | `true` |
| `EMAIL_NOTIFY_HELMET`, `EMAIL_NOTIFY_VEST`, `EMAIL_NOTIFY_COMBINED` ✱ | `true` | Email per violation type | `true` |
| `SMTP_HOST` ✱ / `SMTP_PORT` ✱ | `smtp.gmail.com` / `587` | SMTP server (STARTTLS) | `smtp.gmail.com` / `587` |
| `SENDER_EMAIL` ✱ | empty | Sending account | `your_email@gmail.com` |
| `RECEIVER_EMAIL` ✱ | empty | Recipient | `receiver_email@example.com` |
| `EMAIL_PASSWORD` ✱ | empty | SMTP password (Gmail: **App Password**). Write-only in the UI | `your_app_password` |
| `WEBHOOK_URL` | empty | Optional: a JSON `POST` is sent per violation | `https://hooks.example.com/alerts` |
| `SLACK_WEBHOOK_URL` | empty | Defined but **not implemented** | – |

All of the above are optional; the minimum to run is no `.env` at all. Email is considered "configured" only when sender, password and recipient are filled in and are not the example placeholders.

> Never put real credentials in `.env.example`, and never commit `.env` (see [Security](#18-security-and-limitations)).

---

## 8. Model configuration

- **Weights:** `Model/ppe.pt` (≈ 24.5 MB), committed to the repository. It is **not** downloaded automatically.
- **Architecture:** the checkpoint's training metadata names `yolov8n.yaml` (YOLOv8-nano, object detection), image size 800, 100 epochs. The training dataset is recorded only as a Google-Drive path (`…/ppe-1/data.yaml`), so its source and size cannot be verified from this repository.
- **Loading:** `PPEDetector` (`app/core/detector.py`) calls `ultralytics.YOLO(MODEL_PATH)` once at server start-up.
- **Classes** (read from the model file itself):

| ID | Class | ID | Class |
|---|---|---|---|
| 0 | Hardhat | 5 | Person |
| 1 | Mask | 6 | Safety Cone |
| 2 | NO-Hardhat | 7 | Safety Vest |
| 3 | NO-Mask | 8 | machinery |
| 4 | NO-Safety Vest | 9 | vehicle |

- **How the app uses them.** It needs `Person`, `Hardhat` and `Safety Vest`. A worker is "missing a helmet/vest" when **no `Hardhat`/`Safety Vest` box lands on their head/torso region**. The model's own `NO-Hardhat`, `NO-Safety Vest`, `NO-Mask`, `Mask`, cone and machinery detections are drawn on the video but are **not** used to decide violations.
- **Confidence.** A detection below the threshold is discarded. `DETECTION_CONFIDENCE` (0.5) applies to people and other objects; `PPE_ITEM_CONFIDENCE` (0.3) applies to Hardhat and Safety Vest, because the model scores hard hats on small or distant workers low. This lower value was chosen after checking a few frames of the bundled demo video (hard hats were missed at 0.5 and found at 0.25); it has **not** been validated on webcam footage. Lowering it makes false "violations" rarer but can wrongly accept non-helmet objects; raising it does the opposite.
- **Worker tracking.** `IoUTracker` matches person boxes between frames (box overlap with motion prediction). A person receives an ID after `TRACK_MIN_HITS` frames. The ID is kept for `TRACK_MAX_AGE` frames while the person is not detected.
- **Auxiliary model.** `yolo11n-pose.pt` (head/torso keypoints). Ultralytics downloads it automatically on first use (internet needed once). If it cannot be loaded the app logs a warning and continues with person boxes only. `ENABLE_POSE=false` skips it.
- **Verify the weights exist:**

```powershell
Get-Item Model\ppe.pt | Select-Object Name, Length      # expect about 24,555,554 bytes
python -c "from ultralytics import YOLO; print(YOLO('Model/ppe.pt').names)"
```

- **Limitations of the model.** Accuracy was not measured here and no perfect accuracy is claimed. Small, distant, dark, partly hidden or unusually dressed workers, and non-standard helmets or vests, can be missed or wrongly flagged. The model was not retrained for this project's dashboard work.

---

## 9. Running the application

```powershell
cd Construction-PPE-Detection
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait for the log lines `YOLO model loaded from Model/ppe.pt` and `Camera manager started`, then:

| What | URL |
|---|---|
| **Dashboard** | http://localhost:8000 |
| Interactive API documentation (Swagger UI) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health (`"model_loaded": true`) |

- **Stop:** press `Ctrl+C` in the PowerShell window. Stop cameras first with **Stop** on *Live Monitoring* (otherwise they are restarted automatically at the next launch).
- **Restart after changing `.env`:** stop the server and run the command again. Values saved on the Settings page apply immediately and survive restarts.
- Avoid `--reload` while a webcam is open; the restart can leave the camera locked.
- Use `--host 0.0.0.0` only if you deliberately want other computers on your network to reach the dashboard (there is no login).

**Backend vs frontend:** you do not start a separate frontend. The same `uvicorn` process serves the dashboard files from `app/static/` at `/`.

---

## 10. User operating guide

Sidebar menu: **Dashboard · Live Monitoring · Violations · Workers · Reports · Settings**. The top-right **bell** shows how many new violations arrived since you opened the page (**Mark all read** clears it); the bottom of the sidebar shows server/model status.

### Dashboard
- Cards for **today**: Workers detected, Compliance, Total violations, Helmet violations, Vest violations, Combined violations.
- **Daily violations – last 7 days** (stacked by type) and **Violation distribution (7 days)**.
- **Recent violations** (click a row for details) and **Cameras** with Running / No signal / Stopped.

### Live Monitoring
1. Pick a camera in the drop-down and press **Start** (**Stop** to end). Add cameras under *Settings → Cameras* first.
2. The video shows the annotated stream. Status chip: **Detecting**, **No signal – camera disconnected?** or **Stopped**.
3. **Detection status** shows the active confidence thresholds, counters (In view, Compliant, No helmet, No vest, Critical, Tracked total) and a table per worker: Worker ID, Helmet OK/Missing, Vest OK/Missing, Confidence.
4. **Live violation alerts** lists new incidents instantly; click one to open it.

**Box colours.** Person boxes use the worker's *status*: 🟩 green = compliant · 🟥 red `No Hardhat` · 🟧 orange `No Vest` · 🟪 magenta, thick border, `CRITICAL: No Hardhat + No Vest`. Other detections use class colours with the class name and confidence (Hardhat blue, Mask green, NO-Hardhat red, NO-Mask cyan, NO-Safety Vest magenta, Safety Cone purple, Safety Vest teal, machinery olive, vehicle grey). Counters at the top-left count Hardhats, Safety Vests and People; "Violation Recorded" appears for 3 s after an incident.

### Violations
- Table: ID, evidence thumbnail, time, worker, type, camera, confidence.
- Filters: **Search** (ID, worker number, camera name, type, date text), **Type**, **Camera**, **From / To** dates, **Reset**; **Previous / Next** pages.
- **Export CSV** downloads the current filter results.
- Click a row for the **detail** window: large screenshot (or "no screenshot available"), missing PPE, worker (link to history), camera, time, confidence, session and **email status** (sent / failed with reason / not sent).

### Workers
Lists tracking IDs with Total / Helmet / Vest / Combined counts, session start and last violation; filter by search, camera, dates, **Only with violations**. Click a row for that worker's full history. **A tracking ID is session-based and does not identify a real person** – there is no face recognition, and the same person can get a new ID after a camera restart or leaving the view.

### Reports
Choose **Daily** (date) or **Monthly** (month). You get summary cards, charts (incidents by hour for daily; daily trend for monthly), a distribution chart and a per-camera table. **Export CSV** saves the report; **Print / Save as PDF** opens the browser print dialog (choose "Save as PDF").
*Compliance %* = workers tracked in the period with no recorded incident ÷ all workers tracked in the period; it shows "—" when no workers were tracked. Worker counts exist only for sessions run after worker tracking records were added.

### Settings
- **Detection & violation rules:** Detection confidence, Helmet / vest confidence, Violation persistence (seconds), Duplicate-prevention cooldown (seconds).
- **Email notifications:** enable switch, SMTP host/port, sender, recipient, app password, and checkboxes for Missing helmet / Missing safety vest / Combined violation. Buttons **Save settings** and **Send test email**.
- **Cameras:** **Add camera** form; table with **Edit** and **Delete** (a camera that has recorded violations asks for a second confirmation before deleting its history too).

---

## 11. Camera setup

**Laptop webcam:** *Settings → Cameras* → Name `Laptop webcam`, Type **Webcam**, Source **`0`** → **Add camera**; then *Live Monitoring* → select it → **Start**. Try `1`, `2` if `0` is not the right device. For a webcam the source **must be a number** (the API rejects anything else).

Also supported (by the code): **RTSP / IP camera** – Type *RTSP / IP camera*, Source e.g. `rtsp://user:password@192.168.1.100:554/stream` (the exact path depends on the camera brand; not tested with real hardware); **Video file** – Type *Video file*, Source a full path such as `C:\videos\site.mp4` (loops).

| Problem | What to do |
|---|---|
| **Permission denied / no frames** | Windows *Settings → Privacy & security → Camera*: allow desktop apps to use the camera |
| **Camera already in use** | Close Zoom, Teams, the Windows Camera app, other browser tabs using the camera. The Start request returns "Could not start camera…" and the server log says `Cannot open webcam index N` |
| **Invalid camera source** | Webcam source must be `0`, `1`…; RTSP needs a full URL; file needs a full existing path. Fix it with **Edit** (stop the camera first) |
| **Black video panel** | Camera not started, started but no frames yet (wait a few seconds), or the stream was lost – press **Stop** then **Start**. Check the status chip and the PowerShell log |
| **Camera disconnected** | After 3 s without frames the status becomes **No signal**; the server tries to reconnect every 5 s and returns to **Detecting** when frames resume |

---

## 12. Violation detection workflow

For every tracked worker and frame the app derives a status and maps it to a violation type:

| Helmet | Vest | Result |
|---|---|---|
| ✔ | ✔ | compliant, nothing recorded |
| ✘ | ✔ | **`NO-Hardhat`** |
| ✔ | ✘ | **`NO-Safety Vest`** |
| ✘ | ✘ | **`COMBINED`** (one incident listing both missing items) |

**Preventing duplicates**
- **Persistence** (`VIOLATION_PERSIST_SECONDS`, default 3 s): the *same* status must last this long. Any change of status (even helmet → helmet + vest) restarts the timer, so flickers are ignored and a changed problem is reported after its own persistence period.
- **Cooldown** (`ALERT_COOLDOWN_SECONDS`): the same worker + same type is not recorded again until the cooldown has passed, even if the problem continues. A *different* type is not blocked by it.
- Frames are never saved one-per-frame; at most one record per worker, type and cooldown.
- Recognition is smoothed (majority vote over `PPE_SMOOTHING_WINDOW` frames) so one missed detection does not flip a compliant worker.

**Recording an incident.** One annotated screenshot of the frame is written; each incident row is saved with worker ID, camera, time, confidence, screenshot path and session ID; the event is pushed to the dashboard; email/webhook are sent in the background.

**Screenshot storage:** `violation_frames/<YYYY-MM-DD>/camera_<id>/violation_<milliseconds>_w<worker IDs>.jpg`. The database stores the path relative to `violation_frames`, and the dashboard serves it at `/frames/...`. The image is the full-resolution frame with boxes, labels and a caption banner.

**If screenshot capture fails** (disk error, etc.), the error is logged and the incident is **still recorded** and alerted, just without a picture; the dashboard shows "no image / no screenshot available". Images deleted later from disk are handled the same way.

---

## 13. Email notifications

Email is **optional**: with no configuration the app records and shows everything and simply sends no email.

1. Open *Settings → Email notifications* and tick **Send email notifications**.
2. Fill in: SMTP host `smtp.gmail.com`, port `587`, sender, recipient, and a Gmail **App Password** ([create one](https://support.google.com/accounts/answer/185833); your normal password will not work). Choose the violation types to email.
3. Press **Save settings**, then **Send test email** (it saves first, then sends; the result is shown as a message).

Equivalent `.env` example (placeholders only):

```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
RECEIVER_EMAIL=receiver_email@example.com
EMAIL_PASSWORD=your_app_password
```

- **Triggers:** each recorded `NO-Hardhat`, `NO-Safety Vest` and `COMBINED` incident whose type is switched on (one email per incident, so cooldown limits email volume).
- **Content:** subject like `[CRITICAL] Missing helmet + vest - worker #3 - Laptop webcam` (`[Alert]` for single violations); body with violation, worker ID, camera, time, confidence, incident number; the screenshot is **attached** when the file exists.
- **Failures:** sending runs in the background with a 20 s SMTP timeout. Errors are logged, stored in `alert_log` and shown in the violation detail ("Email failed: …"). They never stop detection.

---

## 14. API documentation

Base path `/api/v1`. Interactive documentation with all schemas is at `/docs`. PowerShell examples use `Invoke-RestMethod`; response values are illustrative.

### Health

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | `{"status":"ok","model_loaded":true,"cameras_active":0}` |
| GET | `/metrics` | Live counts per running camera |

### Cameras

| Method | Endpoint | Purpose / parameters |
|---|---|---|
| GET | `/cameras` | List cameras with `is_running` and `status` (`stopped` / `running` / `no_signal`) |
| POST | `/cameras` | Body `{"name","source_type":"webcam\|rtsp\|file","source_uri"}`; webcam URI must be a number (else 422) |
| GET | `/cameras/{camera_id}` | One camera |
| PUT | `/cameras/{camera_id}` | Body `{"name"?, "source_uri"?}`; 409 if running and changing the source |
| DELETE | `/cameras/{camera_id}` | `delete_history=true` also deletes its violations; otherwise 409 if any exist |
| POST | `/cameras/{camera_id}/start` | Start processing; 400 if the source cannot be opened |
| POST | `/cameras/{camera_id}/stop` | Stop processing |
| GET | `/stream/{camera_id}` | MJPEG video (`multipart/x-mixed-replace`); 404 if not running |
| WS | `/ws/{camera_id}` | JSON live counts and per-worker status; `{"ping": true}` keep-alives |

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/cameras -ContentType "application/json" `
  -Body '{"name":"Laptop webcam","source_type":"webcam","source_uri":"0"}'
# -> id, name, source_type, source_uri, is_active, created_at, is_running, status
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/cameras/1/start
# -> status: started, camera_id: 1
```

### Violations

| Method | Endpoint | Purpose / parameters |
|---|---|---|
| GET | `/violations` | `camera_id`, `violation_type` (`NO-Hardhat`, `NO-Safety Vest`, `COMBINED`), `worker_id`, `session_id`, `search`, `from`, `to` (ISO date-times), `page` (≥1), `page_size` (1–200, default 50) |
| GET | `/violations/{violation_id}` | One violation plus `alerts` (email/db results) |
| GET | `/violations/export` | CSV; filters `camera_id`, `violation_type`, `worker_id`, `search`, `from`, `to` |

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/violations?violation_type=COMBINED&page_size=5"
```
```json
{ "total": 1, "page": 1, "page_size": 5, "items": [ {
  "id": 5, "camera_id": 1, "camera_name": "Laptop webcam", "violation_type": "COMBINED",
  "label": "Missing helmet + vest", "missing_items": ["Hardhat", "Safety Vest"],
  "confidence": 0.76, "timestamp": "2026-11-17T11:22:09.576648", "track_id": 2,
  "session_id": "2026-11-17 11:21:40", "frame_path": "2026-11-17/camera_1/violation_….jpg",
  "frame_url": "/frames/2026-11-17/camera_1/violation_….jpg", "screenshot_available": true } ] }
```
`frame_url` is `null` and `screenshot_available` is `false` when the image file is missing.

### Workers

| Method | Endpoint | Purpose / parameters |
|---|---|---|
| GET | `/workers` | `camera_id`, `from`, `to`, `only_with_violations`, `search`. Each item: `camera_id`, `camera_name`, `session_id`, `track_id`, counts, `first_seen`, `last_violation` |
| GET | `/workers/history` | Required `camera_id`, `track_id`; optional `session_id`. Totals plus the worker's violations |

### Reports and overview

| Method | Endpoint | Purpose / parameters |
|---|---|---|
| GET | `/overview` | Dashboard data: today's report, 7-day trend, distribution, camera statuses |
| GET | `/reports/daily` | `date=YYYY-MM-DD` (default today) |
| GET | `/reports/monthly` | `month=YYYY-MM` (default this month; invalid → 422) |
| GET | `/reports/daily/export`, `/reports/monthly/export` | The same reports as CSV |

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/reports/daily?date=2026-11-17"
# helmet_violations, vest_violations, combined_violations, total_incidents, workers_detected,
# compliant_workers, workers_with_incidents, compliance_pct (null if no workers), by_hour[24], by_camera[], note
```

### Settings

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/settings` | Current values; password is never returned (`email_password_set`, `email_configured` flags instead) |
| PUT | `/settings` | Partial update; fields: `detection_confidence`, `ppe_item_confidence` (0.05–0.95), `violation_persist_seconds` (0–60), `alert_cooldown_seconds` (0–3600), `email_enabled`, `email_notify_helmet/vest/combined`, `smtp_host`, `smtp_port`, `sender_email`, `receiver_email`, `email_password` (blank keeps the old one) |
| POST | `/settings/test-email` | Sends a test email; returns `{"ok": bool, "message": "..."}` |

### Event streaming

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/events` | Server-Sent Events. One event per new incident: `event: violation` with JSON `{id, camera_id, camera_name, track_id, violation_type, label, confidence, timestamp, frame_url, screenshot_available}`. Keep-alive comments every 15 s |

```powershell
curl.exe -N http://localhost:8000/api/v1/events
```

Other URLs: `/frames/<path>` serves screenshots; `/` serves the dashboard.

---

## 15. Database

- **Engine:** SQLite via SQLAlchemy/aiosqlite. **Location:** `ppe_detection.db` in the project folder (`DATABASE_URL`). The file is git-ignored. (A PostgreSQL URL is possible with `requirements/prod.txt`, but only SQLite was tested.)
- **Initialisation / migration:** `init_db()` (`app/db/session.py`) runs at every start: it creates missing tables and adds the `track_id` and `session_id` columns to an older `violations` table. There are no Alembic migrations.

| Table | Purpose |
|---|---|
| `cameras` | id, name, `source_type` (webcam / rtsp / file), `source_uri`, `is_active`, `created_at` |
| `violations` | id, `camera_id`, `violation_type`, `confidence`, `timestamp` (local time), `frame_path` (relative to `violation_frames`), `track_id`, `session_id`, `resolved_at` (unused) |
| `alert_log` | Result per alert channel for a violation (`db`, `email`): `handler_type`, `sent_at`, `success`, `error_msg` |
| `worker_sightings` | One row per tracked worker per camera session (`camera_id`, `session_id`, `track_id`, `first_seen`); the denominator for compliance % |
| `app_settings` | `key` / `value` pairs saved from the Settings page (may include the email password in plain text) |

**Session IDs.** Tracking IDs restart from 1 every time a camera is started. A *session ID* (the start time of that camera run, e.g. `2026-11-17 11:21:40`) is stored with each violation and sighting, so "worker #3" of one run is never mixed up with "worker #3" of another. A worker is identified in the app by `(camera, session, tracking ID)`.

**Browse data:**
```powershell
python -c "import sqlite3; c=sqlite3.connect('ppe_detection.db'); print(c.execute('select id,violation_type,track_id,timestamp from violations order by id desc limit 10').fetchall())"
```

**Back up** (stop the server first so the file is not in use):
```powershell
New-Item -ItemType Directory -Force backup | Out-Null
Copy-Item ppe_detection.db "backup\ppe_detection-$(Get-Date -Format yyyyMMdd-HHmm).db"
Copy-Item violation_frames "backup\violation_frames-$(Get-Date -Format yyyyMMdd)" -Recurse   # screenshots
```
**Reset test data:** stop the server, delete `ppe_detection.db` and the contents of `violation_frames\`; a new empty database is created on the next start.

---

## 16. Testing

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements/dev.txt
python -m pytest tests -q                                       # whole suite
python -m pytest tests/unit/test_violation_checker.py -q        # one file
python -m pytest tests -k "combined" -q                         # tests matching a name
python -m pytest tests --cov=app --cov-report=term-missing      # coverage
```

**Verified result** (run while preparing this README, Python 3.14.6): **89 passed**. Tests use an in-memory database and mock the camera manager and model, so no webcam or GPU is needed.

**Covered by automated tests:** helmet-only, vest-only and combined classification; persistence timing; cooldown; change of violation type; no duplicate records per frame; multiple workers; tracker and PPE assignment logic; per-class detection thresholds; screenshots (date/camera folders, missing file, path safety, shared image); event bus; camera disconnect ("No signal" and reconnect attempts); email (not configured, disabled, success, failure, attachment); daily/monthly reports including empty periods and zero-worker compliance; violation filters; workers endpoints; settings validation, persistence and password handling; camera validation and deletion rules; CSV exports.

**Needs manual testing:** the browser dashboard (layout, charts, notifications, print to PDF), a real webcam, real RTSP cameras, real SMTP delivery, and detection accuracy on real workers and PPE.

**Practical test scenarios** (stand 1–2 m from the camera with good light; default persistence is 3 s):

| # | Scenario | Expected result | How to verify |
|---|---|---|---|
| 1 | Wearing helmet and vest | Green box, `ID n`, no incident | *Live Monitoring* shows Compliant 1; no new row in *Violations* |
| 2 | Without helmet (vest on) | Red box; after ~3 s a `NO-Hardhat` incident | New row, toast, bell counter; screenshot in `violation_frames\<date>\camera_<id>\` |
| 3 | Without vest (helmet on) | Orange box; after ~3 s a `NO-Safety Vest` incident | Same, type "Missing safety vest" |
| 4 | Without both | Magenta `CRITICAL` box; **one** `COMBINED` incident | Exactly one row for that worker and moment |
| 5 | Several workers | Separate IDs and colours; separate incidents per worker | Worker table on *Live Monitoring*; *Workers* page |
| 6 | Camera unavailable | Start fails with "Could not start camera…" or, if unplugged while running, status **No signal** | Message on screen; log; status chip |
| 7 | Screenshot check | Thumbnail in table, large image in detail | Open the saved `.jpg`; delete it and reopen the violation: shows "no screenshot available" |
| 8 | Email | Test email arrives; incident emails carry the picture | *Settings → Send test email*; violation detail shows "Email sent" or the failure reason |
| 9 | Daily report | Counts match the Violations list for that date | *Reports → Daily*; compare; try **Export CSV** |
| 10 | Monthly report | Totals and daily trend match; most frequent type shown | *Reports → Monthly*; **Print / Save as PDF** |

No real PPE? Hold a phone photo of a worker in front of the webcam, or add a **Video file** camera pointing at `Visuals\ppe-detection-demo.mp4`.

---

## 17. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Run from the project folder: `cd Construction-PPE-Detection`, and start with `python -m uvicorn app.main:app` |
| `ModuleNotFoundError` for any other module / "FastAPI not installed" / `uvicorn` not found | The venv is not active or dependencies are missing: `.\venv\Scripts\Activate.ps1`, then `python -m pip install -r requirements/dev.txt`. Check with `python -m pip list` |
| Uvicorn startup error | Read the last lines: *port in use* → use `--port 8001`; *model not found* → check `MODEL_PATH` and that you are in the project folder; *database locked* → close other programs using `ppe_detection.db` |
| Python version problems | Use Python 3.11 (`py -3.11 -m venv venv`). Versions below 3.11 are not supported by `pyproject.toml`. If a package has no wheel for a very new Python, switch to 3.11 |
| PyTorch install errors | Upgrade pip (`python -m pip install --upgrade pip`), use 64-bit Python 3.11, ensure free disk space (several GB) and a stable connection; retry the install |
| Ultralytics model loading errors | Confirm `Model\ppe.pt` is ≈ 24.5 MB and not an empty/partial file (`git checkout -- Model/ppe.pt` restores it). Upgrading Ultralytics major versions can change loading behaviour; try `python -m pip install -r requirements/base.txt` again |
| Missing model weights | Restore with `git checkout -- Model/ppe.pt` or copy your own weights and set `MODEL_PATH`. The pose weights are different: they download automatically; if offline the app continues without pose |
| Webcam not opening | See [Camera setup](#11-camera-setup) |
| No PPE detections | Improve lighting, stand closer with head and torso visible, lower *Detection confidence* (and *Helmet / vest confidence*), wait ~1 s for the worker ID, check the camera is **Detecting** |
| False detections ("No Hardhat" although wearing one) | Typically distance, darkness or a hidden head. Move closer, light the scene, lower *Helmet / vest confidence*. If non-helmets are accepted, raise it. Use a longer *Violation persistence* to ignore short glitches |
| Dashboard not loading | Is the server running? Open `/api/v1/health`. Use `http://localhost:8000` (the port you chose). Hard-refresh with Ctrl+F5 |
| Black video stream | Press **Stop**, then **Start**; make sure only one program uses the camera; check the log for `Cannot open webcam index` |
| Database migration errors | The app adds missing columns automatically. If the file is damaged or from another project, back it up and delete `ppe_detection.db` (a fresh one is created) |
| SMTP authentication error (`535`) | Gmail needs an **App Password** (with 2-step verification enabled), not your account password. Check sender, host `smtp.gmail.com`, port `587`; see "Email failed: …" in the violation detail |
| Slow CPU inference | Set `ENABLE_POSE=false` in `.env`, use a lower camera resolution, close other heavy programs, or use a GPU-enabled PyTorch if you have a CUDA GPU |

---

## 18. Security and limitations

- **Never commit `.env`.** It is listed in `.gitignore`, **but this repository's history already tracks a `.env` file**. If you ever put real values in it, run `git rm --cached .env` and rotate any exposed password.
- **Keep SMTP credentials private.** Use a Gmail App Password, not your main password; do not paste credentials into screenshots, issues or commits.
- **Password storage.** If you type the email password on the Settings page, it is stored **unencrypted** in the local SQLite file (`app_settings`). It is never shown in the UI or returned by the API. Alternatively keep it only in `.env`. Protect or delete the database accordingly.
- **No authentication.** Anyone who can reach the server can view and change everything. Bind to `127.0.0.1` (as in the commands above) unless you deliberately want network access.
- **Tracking IDs are not facial recognition.** No faces are recognised or stored as identities; the ID is a number per camera session.
- **Model accuracy** depends on the training data, lighting, distance, camera quality and clothing. No accuracy figure is claimed.
- **Screenshots contain images of people**; handle and delete them according to your privacy rules.
- **Academic prototype.** This is a final-year project demonstration and **not a certified industrial safety system**. Do not rely on it as the only safety control.
- Other limits: IDs may change after occlusion or restart; compliance % counts tracking IDs; PDF export is the browser's print function; deleting a camera does not remove its screenshot files; the Docker/PostgreSQL setup and RTSP cameras were not tested for this documentation; the browser UI has only been checked manually.

---

## 19. Screenshots

The images below are placeholders: **no screenshots of the current dashboard are included in the repository yet.** To add them, create a `docs/screenshots/` folder, save PNG files with these names, then replace each "to be added" cell with `![Name](docs/screenshots/file.png)`.

| Screen | File to add | Status |
|---|---|---|
| Dashboard | `docs/screenshots/dashboard.png` | to be added |
| Live Monitoring | `docs/screenshots/live-monitoring.png` | to be added |
| Helmet violation (red) | `docs/screenshots/violation-helmet.png` | to be added |
| Safety vest violation (orange) | `docs/screenshots/violation-vest.png` | to be added |
| Combined violation (critical) | `docs/screenshots/violation-combined.png` | to be added |
| Violation history | `docs/screenshots/violations.png` | to be added |
| Workers page | `docs/screenshots/workers.png` | to be added |
| Reports page | `docs/screenshots/reports.png` | to be added |
| Settings page | `docs/screenshots/settings.png` | to be added |

Existing project media from the original repository: [`Visuals/ppe-detection-demo.mp4`](Visuals/ppe-detection-demo.mp4), [`Visuals/demo-tracking-pose.gif`](Visuals/demo-tracking-pose.gif) and banner images in `Visuals/`. Evidence screenshots generated by your own runs are in `violation_frames/`.

---

## 20. Future enhancements

- Retrain or fine-tune the model on a larger, more diverse PPE dataset (different lighting, distances, helmet colours, vest types) and report measured precision/recall.
- Use the model's `NO-Hardhat` / `NO-Safety Vest` classes as a second opinion, or add more PPE (gloves, boots, goggles).
- More robust worker tracking (appearance features, re-identification) while respecting privacy.
- Better multi-camera support: per-camera thresholds and a side-by-side wall of feeds.
- Advanced analytics: shift-based reports, heat maps, long-term trends, server-generated PDF reports.
- Secure credential storage (encrypted secrets or the OS credential store) and login with roles.
- Deployment to a server or edge device (Docker is provided but untested here), with PostgreSQL if needed.
- Image/video upload for offline analysis; real Slack/Teams notifications.

---

## 21. License and credits

Licensed under the **MIT License** – see [LICENSE](LICENSE). See also [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [SECURITY.md](SECURITY.md).

Built with [Ultralytics YOLO](https://github.com/ultralytics/ultralytics), [FastAPI](https://fastapi.tiangolo.com/), [OpenCV](https://opencv.org/), [PyTorch](https://pytorch.org/) and [SQLAlchemy](https://www.sqlalchemy.org/). Original repository: <https://github.com/Ansarimajid/Construction-PPE-Detection>.
