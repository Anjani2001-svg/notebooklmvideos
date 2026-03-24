#!/usr/bin/env python3
"""
SLC Video Merger — Railway Edition
Per-session isolation · FFmpeg processing · Multi-user safe
"""

import os
import uuid
import subprocess
import time
import shutil
import threading
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# ─────────────────────────── PAGE CONFIG ────────────────────────────────
st.set_page_config(
    page_title="SLC Video Merger",
    page_icon="🎬",
    layout="wide",
)

# ─────────────────────────── PATHS ──────────────────────────────────────
BASE_DIR   = Path(__file__).parent
INTRO_TPL  = BASE_DIR / "assets" / "intro_template.mp4"
OUTRO_TPL  = BASE_DIR / "assets" / "outro_template.mp4"   # optional fixed outro
TMP_ROOT   = Path("/tmp/slc_merger")
TMP_ROOT.mkdir(parents=True, exist_ok=True)

# ─────────────────────────── FONTS ──────────────────────────────────────
def _find_font(name):
    candidates = [
        str(BASE_DIR / "fonts" / name),
        f"/usr/share/fonts/truetype/google-fonts/{name}",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

BOLD   = _find_font("Poppins-Bold.ttf")
MEDIUM = _find_font("Poppins-Medium.ttf")
TEAL   = (96, 204, 190)
WHITE  = (255, 255, 255)

# ─────────────────────────── SESSION INIT ───────────────────────────────
def get_session_dir() -> Path:
    """Create a unique temp directory per browser session."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    d = TMP_ROOT / st.session_state.session_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def cleanup_session(session_dir: Path):
    """Delete the session temp directory after download."""
    try:
        shutil.rmtree(session_dir, ignore_errors=True)
    except Exception:
        pass

def cleanup_old_sessions(max_age_seconds=3600):
    """Background cleanup of sessions older than 1 hour."""
    now = time.time()
    for d in TMP_ROOT.iterdir():
        if d.is_dir():
            age = now - d.stat().st_mtime
            if age > max_age_seconds:
                shutil.rmtree(d, ignore_errors=True)

# ─────────────────────────── PILLOW HELPERS ─────────────────────────────
def _ft(path, size):
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

def _text_bbox(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]

def render_intro_overlay(course, unit_num, unit_title, W=1920, H=1080):
    """Transparent 1920×1080 RGBA PNG with course text + teal badge."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Course name ──────────────────────────────────────────────────────
    f_course = _ft(BOLD, 52)
    cw, ch   = _text_bbox(draw, course, f_course)
    cx       = (W - cw) // 2
    cy       = H // 2 - 110
    draw.text((cx + 2, cy + 2), course, font=f_course, fill=(0, 0, 0, 120))
    draw.text((cx, cy), course, font=f_course, fill=WHITE)

    # ── Unit badge ───────────────────────────────────────────────────────
    f_unit = _ft(BOLD, 44)
    uw, uh = _text_bbox(draw, unit_num, f_unit)
    pad    = 24
    bx     = (W - uw - pad * 2) // 2
    by     = cy + ch + 24
    bw     = uw + pad * 2
    bh     = uh + pad
    r      = 14
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=r, fill=(*TEAL, 230))
    draw.text((bx + pad, by + pad // 2), unit_num, font=f_unit, fill=WHITE)

    # ── Unit title ───────────────────────────────────────────────────────
    if unit_title.strip():
        f_title = _ft(MEDIUM, 36)
        tw, _   = _text_bbox(draw, unit_title, f_title)
        tx      = (W - tw) // 2
        ty      = by + bh + 22
        draw.text((tx + 1, ty + 1), unit_title, font=f_title, fill=(0, 0, 0, 100))
        draw.text((tx, ty), unit_title, font=f_title, fill=WHITE)

    return img

def render_outro_overlay(W=1920, H=1080):
    """Simple 'END' badge for outro frame."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    f    = _ft(BOLD, 72)
    tw, th = _text_bbox(draw, "END", f)
    pad  = 36
    bx   = (W - tw - pad * 2) // 2
    by   = (H - th - pad) // 2
    draw.rounded_rectangle([bx, by, bx + tw + pad * 2, by + th + pad], radius=18, fill=(*TEAL, 230))
    draw.text((bx + pad, by + pad // 2), "END", font=f, fill=WHITE)
    return img

# ─────────────────────────── FFMPEG HELPERS ─────────────────────────────
def _run(cmd, label=""):
    result = subprocess.run(
        cmd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error ({label}):\n{result.stderr[-800:]}")
    return result

def save_png(img: Image.Image, path: Path):
    img.save(str(path), "PNG")

def make_intro_video(
    course, unit_num, unit_title,
    session_dir: Path,
    rise_duration=0.8, fps=25
) -> Path:
    overlay_png = session_dir / "intro_overlay.png"
    intro_out   = session_dir / "intro_final.mp4"

    overlay = render_intro_overlay(course, unit_num, unit_title)
    save_png(overlay, overlay_png)

    # Overlay with rise animation (translate Y from +60 → 0, fade in)
    rise_frames = int(rise_duration * fps)
    vf = (
        f"overlay=0:0:enable='gte(t,0)',"
        f"fade=in:st=0:d={rise_duration}"
    )

    if not INTRO_TPL.exists():
        # No template — create a 5-second black intro with overlay
        _run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r={fps}:d=5",
            "-i", str(overlay_png),
            "-filter_complex",
            f"[0:v][1:v]overlay=0:0,fade=in:st=0:d={rise_duration}[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-t", "5",
            str(intro_out)
        ], "intro_no_template")
    else:
        _run([
            "ffmpeg", "-y",
            "-i", str(INTRO_TPL),
            "-i", str(overlay_png),
            "-filter_complex",
            f"[0:v][1:v]overlay=0:0,fade=in:st=0:d={rise_duration}[v]",
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(intro_out)
        ], "intro_with_template")

    return intro_out

def make_outro_video(session_dir: Path, duration=4, fps=25) -> Path:
    overlay_png = session_dir / "outro_overlay.png"
    outro_out   = session_dir / "outro_final.mp4"

    if OUTRO_TPL.exists():
        shutil.copy(str(OUTRO_TPL), str(outro_out))
        return outro_out

    overlay = render_outro_overlay()
    save_png(overlay, overlay_png)

    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r={fps}:d={duration}",
        "-i", str(overlay_png),
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(outro_out)
    ], "outro")

    return outro_out

def normalize_content(uploaded_path: Path, session_dir: Path) -> Path:
    norm_out = session_dir / "content_norm.mp4"
    _run([
        "ffmpeg", "-y", "-i", str(uploaded_path),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2",
        str(norm_out)
    ], "normalize")
    return norm_out

def merge_videos(parts: list, session_dir: Path) -> Path:
    concat_txt = session_dir / "concat.txt"
    final_out  = session_dir / "final_output.mp4"

    with open(concat_txt, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")

    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
        "-c", "copy",
        str(final_out)
    ], "merge")

    return final_out

# ─────────────────────────── CUSTOM CSS ─────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0a2a3c; color: #ffffff; }
    .main-header {
        background: linear-gradient(135deg, #0d3b54 0%, #0a2a3c 100%);
        padding: 2rem; border-radius: 12px;
        border-left: 4px solid #60ccbe;
        margin-bottom: 1.5rem;
    }
    .status-box {
        background: #0d3b54; border-left: 4px solid #60ccbe;
        padding: 1rem 1.5rem; border-radius: 8px;
        margin: 0.5rem 0;
    }
    .step-done  { color: #60ccbe; font-weight: 600; }
    .step-active{ color: #ffffff; font-weight: 600; }
    .step-wait  { color: #6b8fa3; }
    .stButton > button {
        background: #60ccbe !important; color: #0a2a3c !important;
        font-weight: 700 !important; border: none !important;
        padding: 0.7rem 2rem !important; border-radius: 8px !important;
        width: 100%;
    }
    .stButton > button:hover { background: #4db8a8 !important; }
    div[data-testid="stFileUploader"] {
        border: 2px dashed #60ccbe !important;
        border-radius: 10px !important;
        background: #0d3b54 !important;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────── HEADER ─────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1 style="color:#60ccbe; margin:0;">🎬 SLC Video Merger</h1>
    <p style="color:#a0c4d4; margin:0.3rem 0 0;">
        Combine branded intro · NotebookLM content · outro into one MP4
    </p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────── SESSION SETUP ──────────────────────────────
session_dir = get_session_dir()

# Background cleanup (non-blocking)
t = threading.Thread(target=cleanup_old_sessions, daemon=True)
t.start()

# ─────────────────────────── SIDEBAR ────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Intro Settings")
    course_name = st.text_input(
        "Course Name",
        value="Level 3 Diploma in Business Administration (RQF)",
        help="Appears at top of intro overlay"
    )
    unit_number = st.text_input(
        "Unit Number",
        value="UNIT 01 | CHAPTER 01",
        help="Shown in teal badge"
    )
    unit_title = st.text_input(
        "Unit Title (optional)",
        value="",
        help="Subtitle below the badge"
    )
    st.markdown("---")
    st.markdown("### 📋 Session Info")
    st.caption(f"Session: `{st.session_state.session_id[:8]}…`")
    st.caption("Each user gets isolated temp storage.")

# ─────────────────────────── MAIN AREA ──────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("#### 📤 Upload NotebookLM Video")
    uploaded = st.file_uploader(
        "Drag & drop your content MP4 here",
        type=["mp4", "mov", "webm", "avi"],
        label_visibility="collapsed"
    )

    if uploaded:
        st.success(f"✅ {uploaded.name}  ({uploaded.size / 1_048_576:.1f} MB)")
        st.video(uploaded)

with col2:
    st.markdown("#### 🔍 Intro Preview")
    if st.button("👁️ Preview Intro Overlay"):
        with st.spinner("Rendering preview…"):
            try:
                img = render_intro_overlay(course_name, unit_number, unit_title)
                buf = BytesIO()
                img.save(buf, "PNG")
                st.image(buf.getvalue(), caption="Intro overlay (transparent areas = video shows through)")
            except Exception as e:
                st.error(f"Preview error: {e}")

# ─────────────────────────── PROCESS ────────────────────────────────────
st.markdown("---")
st.markdown("#### 🚀 Merge Videos")

if st.button("▶ Start Merging", disabled=(uploaded is None)):

    if not uploaded:
        st.warning("Please upload a content video first.")
    else:
        # ── Status panel ────────────────────────────────────────────────
        status_area = st.empty()

        def show_status(steps):
            icons = {"done": "✅", "active": "⏳", "wait": "⬜"}
            html  = '<div class="status-box">'
            for label, state in steps:
                cls  = f"step-{state}"
                icon = icons[state]
                html += f'<p class="{cls}" style="margin:0.3rem 0;">{icon} {label}</p>'
            html += "</div>"
            status_area.markdown(html, unsafe_allow_html=True)

        steps = [
            ("Saving uploaded video",       "active"),
            ("Building custom intro",       "wait"),
            ("Normalising content video",   "wait"),
            ("Building outro",              "wait"),
            ("Merging everything",          "wait"),
            ("Ready to download!",          "wait"),
        ]
        show_status(steps)
        prog = st.progress(0)

        try:
            # Step 1 — save upload
            upload_path = session_dir / f"upload_{uploaded.name}"
            with open(upload_path, "wb") as f:
                f.write(uploaded.read())
            steps[0] = (steps[0][0], "done")
            steps[1] = (steps[1][0], "active")
            show_status(steps); prog.progress(15)

            # Step 2 — intro
            intro_path = make_intro_video(course_name, unit_number, unit_title, session_dir)
            steps[1] = (steps[1][0], "done")
            steps[2] = (steps[2][0], "active")
            show_status(steps); prog.progress(35)

            # Step 3 — normalise content
            norm_path = normalize_content(upload_path, session_dir)
            steps[2] = (steps[2][0], "done")
            steps[3] = (steps[3][0], "active")
            show_status(steps); prog.progress(60)

            # Step 4 — outro
            outro_path = make_outro_video(session_dir)
            steps[3] = (steps[3][0], "done")
            steps[4] = (steps[4][0], "active")
            show_status(steps); prog.progress(75)

            # Step 5 — merge
            final_path = merge_videos([intro_path, norm_path, outro_path], session_dir)
            steps[4] = (steps[4][0], "done")
            steps[5] = (steps[5][0], "active")
            show_status(steps); prog.progress(95)

            # Step 6 — done
            steps[5] = (steps[5][0], "done")
            show_status(steps); prog.progress(100)

            st.success("🎉 Merge complete! Your video is ready.")

            # Read output bytes
            with open(final_path, "rb") as f:
                video_bytes = f.read()

            file_size_mb = len(video_bytes) / 1_048_576
            st.info(f"📦 Output size: {file_size_mb:.1f} MB")

            safe_name = (
                f"{unit_number.replace('|','').replace(' ','_').strip()}_"
                f"{course_name[:30].replace(' ','_')}.mp4"
            )

            st.download_button(
                label="⬇️ Download Merged Video",
                data=video_bytes,
                file_name=safe_name,
                mime="video/mp4",
                use_container_width=True,
            )

            # Schedule cleanup after download
            cleanup_thread = threading.Thread(
                target=lambda: (time.sleep(300), cleanup_session(session_dir)),
                daemon=True
            )
            cleanup_thread.start()

        except RuntimeError as e:
            st.error(f"❌ Processing failed:\n\n```\n{e}\n```")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
        finally:
            prog.empty()
