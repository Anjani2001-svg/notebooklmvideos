# SLC Video Merger — Railway Edition

Multi-user safe Streamlit app for merging NotebookLM videos with branded SLC intro/outro.

## What It Does

`Custom Intro → NotebookLM Content → Outro` → single downloadable MP4

- Per-session isolated temp directories (no user collisions)
- Live status steps during processing
- Auto-cleanup of temp files after 5 minutes post-download
- Background purge of sessions older than 1 hour

---

## Deploy to Railway

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ORG/slc-video-merger.git
git push -u origin main
```

### 2. Create Railway Project
1. Go to [railway.app](https://railway.app)
2. **New Project → Deploy from GitHub repo**
3. Select `slc-video-merger`
4. Railway auto-detects the `Dockerfile` — no extra config needed

### 3. Set Memory (Important)
In Railway dashboard:
- Go to your service → **Settings → Resources**
- Set RAM to **2 GB minimum** (4 GB recommended for concurrent users)

### 4. Add Assets (Optional)
Upload your branded video files to the `assets/` folder before deploying:
```
assets/
├── intro_template.mp4   ← Your animated SLC intro
└── outro_template.mp4   ← Your SLC outro (optional)
```
If these files are absent, the app auto-generates plain black intro/outro with overlays.

### 5. Custom Domain
In Railway → **Settings → Domains** → Add your custom domain or use the generated `.railway.app` URL.

---

## Project Structure

```
slc-video-merger/
├── app.py                    # Main Streamlit app
├── requirements.txt          # Python dependencies (Streamlit, Pillow)
├── Dockerfile                # Railway build (installs FFmpeg + Poppins)
├── railway.toml              # Railway config
├── .streamlit/
│   └── config.toml           # Theme + upload size settings
├── assets/
│   ├── intro_template.mp4    # (add your own)
│   └── outro_template.mp4    # (add your own, optional)
└── README.md
```

---

## Local Development

```bash
# Requires FFmpeg installed locally
# Ubuntu: sudo apt install ffmpeg
# Mac:    brew install ffmpeg

pip install -r requirements.txt
streamlit run app.py
# → http://localhost:8501
```

---

## Multi-User Safety

| Feature | How it works |
|---|---|
| Session isolation | Each browser tab gets a UUID-based `/tmp/slc_merger/{uuid}/` folder |
| File collision prevention | All intermediate files scoped to session dir |
| Auto-cleanup | Temp files deleted 5 min after download |
| Background purge | Sessions >1hr old purged on each new visitor |
| RAM sizing | 2–4 GB on Railway handles ~3–5 concurrent merges |
