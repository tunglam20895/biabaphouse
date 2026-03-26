"""
create_videos.py
────────────────
Luồng cho mỗi sản phẩm:
  1. Tải nhiều ảnh sản phẩm từ image_url (hỗ trợ nhiều URL cách nhau bởi |)
  2. FFmpeg ghép slideshow nhiều ảnh có hiệu ứng chuyển cảnh fade
  3. Tạo voiceover tiếng Việt bằng ElevenLabs
  4. Ghép audio vào video bằng FFmpeg
  5. Lưu video final vào videos/final/

Cấu trúc products.csv:
  - Cột image_url: 1 link hoặc nhiều link cách nhau bởi | (pipe)
    Ví dụ: https://img1.jpg|https://img2.jpg|https://img3.jpg
"""

import os, json, csv, time, requests, subprocess, logging, sys, textwrap
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ── Đường dẫn ────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent
DATA_DIR      = BASE_DIR / "data"
VIDEOS_DIR    = BASE_DIR / "videos"
RAW_DIR       = VIDEOS_DIR / "raw"          # ảnh sản phẩm tải về
AUDIO_DIR     = VIDEOS_DIR / "audio"        # voiceover mp3
FINAL_DIR     = VIDEOS_DIR / "final"        # video ghép xong

for d in [RAW_DIR, AUDIO_DIR, FINAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SCRIPTS_JSON   = DATA_DIR / "scripts_output.json"
PRODUCTS_CSV   = DATA_DIR / "products.csv"
VIDEOS_JSON    = DATA_DIR / "videos_ready.json"

# ── API Keys ──────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID           = os.getenv("VOICE_ID", "")

# ── Slideshow config ──────────────────────────────────────────────────────────
SLIDE_DURATION   = 3.0    # giây mỗi ảnh hiển thị
FADE_DURATION    = 0.5    # giây hiệu ứng fade chuyển cảnh
OUTPUT_WIDTH     = 1080   # TikTok 9:16
OUTPUT_HEIGHT    = 1920
MAX_VIDEO_SECS   = 60     # TikTok giới hạn 60 giây


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 1 — Tải ảnh sản phẩm (hỗ trợ nhiều URL)
# ════════════════════════════════════════════════════════════════════════════

def download_images(product_id: str, image_url_raw: str) -> list[Path]:
    """
    Tải ảnh sản phẩm về máy.
    image_url_raw: 1 URL hoặc nhiều URL cách nhau bởi | (pipe)
    Trả về list các Path ảnh đã tải.
    """
    if not image_url_raw:
        log.warning(f"  ⚠️  Không có image_url — bỏ qua bước tạo video")
        return []

    urls = [u.strip() for u in image_url_raw.split("|") if u.strip()]
    paths = []

    for idx, url in enumerate(urls):
        ext      = Path(url.split("?")[0]).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"
        out_path = RAW_DIR / f"{product_id}_{idx}{ext}"

        if out_path.exists():
            log.info(f"  📁 Ảnh đã có: {out_path.name}")
            paths.append(out_path)
            continue

        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            out_path.write_bytes(resp.content)
            log.info(f"  ✅ Tải ảnh {idx+1}/{len(urls)}: {out_path.name}")
            paths.append(out_path)
        except Exception as e:
            log.error(f"  ❌ Lỗi tải ảnh {idx+1}: {e}")

    return paths


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 2 — Tạo slideshow bằng FFmpeg
# ════════════════════════════════════════════════════════════════════════════

def create_slideshow(product_id: str, image_paths: list[Path],
                     target_duration: float) -> Path | None:
    """
    FFmpeg tạo slideshow từ nhiều ảnh với hiệu ứng fade chuyển cảnh.
    target_duration: tổng thời lượng video (theo độ dài audio)
    """
    out_path = FINAL_DIR / f"{product_id}_slide.mp4"
    if out_path.exists():
        log.info(f"  📁 Slideshow đã có: {out_path.name}")
        return out_path

    if not image_paths:
        log.error("  ❌ Không có ảnh để tạo slideshow")
        return None

    log.info(f"  🎬 Tạo slideshow từ {len(image_paths)} ảnh ({target_duration:.1f}s)...")

    # Tính slide_duration để vừa đủ target_duration
    n = len(image_paths)
    slide_dur = max(SLIDE_DURATION, target_duration / n)

    # Build FFmpeg filter_complex cho slideshow với fade
    # Mỗi ảnh: scale → pad → setpts → fade in/out
    inputs = []
    for p in image_paths:
        inputs += ["-loop", "1", "-t", str(slide_dur + FADE_DURATION), "-i", str(p)]

    # Filter: scale + pad mỗi ảnh về 1080x1920
    filter_parts = []
    for i in range(n):
        filter_parts.append(
            f"[{i}:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps=30[v{i}]"
        )

    # Nối các clip với xfade
    if n == 1:
        # Chỉ 1 ảnh: zoom in nhẹ (Ken Burns)
        filter_complex = (
            f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps=30,"
            f"zoompan=z='min(zoom+0.0015,1.5)':d={int(target_duration*30)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}[vout]"
        )
        map_arg = "[vout]"
    else:
        # Nhiều ảnh: xfade
        fc = ";".join(filter_parts)

        # Chain xfade
        prev = "v0"
        xfade_parts = []
        for i in range(1, n):
            offset = slide_dur * i - FADE_DURATION * i
            curr   = f"xf{i}"
            xfade_parts.append(
                f"[{prev}][v{i}]xfade=transition=fade:"
                f"duration={FADE_DURATION}:offset={offset:.2f}[{curr}]"
            )
            prev = curr

        filter_complex = fc + ";" + ";".join(xfade_parts)
        map_arg = f"[{prev}]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", map_arg,
        "-t", str(min(target_duration, MAX_VIDEO_SECS)),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            log.error(f"  ❌ FFmpeg slideshow lỗi:\n{result.stderr[-800:]}")
            return None
        log.info(f"  ✅ Slideshow xong: {out_path.name}")
        return out_path
    except subprocess.TimeoutExpired:
        log.error("  ❌ FFmpeg timeout")
        return None
    except FileNotFoundError:
        log.error("  ❌ FFmpeg chưa cài. Tải tại: https://ffmpeg.org/download.html")
        return None


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 3 — Tạo voiceover bằng ElevenLabs
# ════════════════════════════════════════════════════════════════════════════

def generate_voiceover(product_id: str, script_text: str) -> Path | None:
    """Gọi ElevenLabs TTS → lưu file mp3."""
    if not ELEVENLABS_API_KEY:
        log.error("❌ ELEVENLABS_API_KEY chưa set trong .env")
        return None
    if not VOICE_ID:
        log.error("❌ VOICE_ID chưa set trong .env — lấy tại elevenlabs.io/app/voice-library")
        return None

    out_path = AUDIO_DIR / f"{product_id}.mp3"
    if out_path.exists():
        log.info(f"  📁 Audio đã có: {out_path.name}")
        return out_path

    log.info("  🎙️  Đang tạo voiceover...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key":   ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": script_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability":         0.5,
            "similarity_boost":  0.75,
            "style":             0.3,
            "use_speaker_boost": True,
        },
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        log.info(f"  ✅ Voiceover xong: {out_path.name}")
        return out_path
    except Exception as e:
        log.error(f"  ❌ Lỗi ElevenLabs: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 4 — Ghép audio vào slideshow bằng FFmpeg
# ════════════════════════════════════════════════════════════════════════════

def get_audio_duration(audio_path: Path) -> float:
    """Lấy độ dài audio bằng ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    try:
        return float(
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        )
    except Exception:
        return 30.0


def merge_audio_video(product_id: str, video_path: Path,
                      audio_path: Path) -> Path | None:
    """FFmpeg ghép voiceover vào slideshow video."""
    out_path = FINAL_DIR / f"{product_id}_final.mp4"
    if out_path.exists():
        log.info(f"  📁 Video final đã có: {out_path.name}")
        return out_path

    log.info("  🔧 Ghép audio + video (FFmpeg)...")
    duration = min(get_audio_duration(audio_path), MAX_VIDEO_SECS)
    log.info(f"  ⏱️  Thời lượng: {duration:.1f}s")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-t", str(duration),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log.error(f"  ❌ FFmpeg merge lỗi:\n{result.stderr[-500:]}")
            return None
        log.info(f"  ✅ Video final: {out_path.name}")
        return out_path
    except subprocess.TimeoutExpired:
        log.error("  ❌ FFmpeg timeout")
        return None
    except FileNotFoundError:
        log.error("  ❌ FFmpeg chưa cài.")
        return None


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def load_scripts() -> list[dict]:
    if not SCRIPTS_JSON.exists():
        log.error(f"❌ Không tìm thấy {SCRIPTS_JSON} — chạy generate_scripts.py trước.")
        return []
    with open(SCRIPTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_products() -> dict:
    if not PRODUCTS_CSV.exists():
        return {}
    with open(PRODUCTS_CSV, "r", encoding="utf-8") as f:
        return {r["product_id"]: r for r in csv.DictReader(f)}


def save_videos_ready(videos: list[dict]):
    existing = []
    if VIDEOS_JSON.exists():
        with open(VIDEOS_JSON, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_ids = {v["product_id"] for v in existing}
    for v in videos:
        if v["product_id"] not in existing_ids:
            existing.append(v)

    with open(VIDEOS_JSON, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    log.info(f"💾 videos_ready.json cập nhật: {len(existing)} video")


def run():
    log.info("=" * 58)
    log.info(f"  create_videos.py  |  {datetime.now():%Y-%m-%d %H:%M}")
    log.info("  Luồng: ảnh sản phẩm → FFmpeg slideshow → voiceover → ghép")
    log.info("=" * 58)

    scripts  = load_scripts()
    products = load_products()

    if not scripts:
        return

    videos_ready = []

    for i, item in enumerate(scripts, 1):
        pid          = item.get("product_id", f"unknown_{i}")
        product_name = item.get("product_name", "")
        script_text  = item.get("script", "") or item.get("content", "")
        image_url    = item.get("image_url", "") or \
                       products.get(pid, {}).get("image_url", "")

        log.info(f"\n[{i}/{len(scripts)}] {product_name[:50]}")
        log.info(f"  product_id: {pid}")

        if not script_text:
            log.warning("  ⚠️  Không có script text — bỏ qua")
            continue

        # ── 1. Tải ảnh ──────────────────────────────────────────────────
        image_paths = download_images(pid, image_url)
        if not image_paths:
            log.warning("  ⚠️  Không có ảnh — bỏ qua")
            continue

        # ── 2. Tạo voiceover trước để biết độ dài ────────────────────────
        audio_path = generate_voiceover(pid, script_text)
        if not audio_path:
            log.warning("  ⚠️  Voiceover thất bại — bỏ qua")
            continue

        # ── 3. Tạo slideshow khớp độ dài audio ───────────────────────────
        audio_duration = get_audio_duration(audio_path)
        target_dur     = min(audio_duration, MAX_VIDEO_SECS)
        slide_path     = create_slideshow(pid, image_paths, target_dur)
        if not slide_path:
            log.warning("  ⚠️  Tạo slideshow thất bại — bỏ qua")
            continue

        # ── 4. Ghép audio + video ────────────────────────────────────────
        final_path = merge_audio_video(pid, slide_path, audio_path)
        if not final_path:
            log.warning("  ⚠️  Ghép video thất bại — bỏ qua")
            continue

        # ── 5. Lưu vào danh sách sẵn sàng đăng ─────────────────────────
        videos_ready.append({
            "product_id":     pid,
            "product_name":   product_name,
            "video_path":     str(final_path),
            "affiliate_link": products.get(pid, {}).get("affiliate_link", ""),
            "script":         script_text,
            "created_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status":         "ready",
        })
        log.info(f"  🎉 Hoàn tất: {final_path.name}")

    if videos_ready:
        save_videos_ready(videos_ready)
        print("\n" + "=" * 58)
        print(f"✅ XONG — {len(videos_ready)} video sẵn sàng đăng TikTok")
        print(f"   Thư mục: {FINAL_DIR}")
        print("=" * 58)
    else:
        log.warning("⚠️  Không có video nào được tạo thành công.")


if __name__ == "__main__":
    run()