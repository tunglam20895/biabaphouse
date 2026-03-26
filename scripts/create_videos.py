"""
create_videos.py
────────────────
Luồng cho mỗi sản phẩm:
  1. Lấy ảnh sản phẩm từ affiliate link (screenshot hoặc URL ảnh)
  2. Gửi ảnh lên fal.ai → Kling image-to-video (~$0.054/video)
  3. Tạo voiceover tiếng Việt bằng ElevenLabs
  4. Ghép audio vào video bằng FFmpeg
  5. Lưu video final vào videos/final/
"""

import os, json, csv, time, requests, subprocess, logging, sys
from pathlib import Path
from datetime import datetime
import base64

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
AI_VIDEO_DIR  = VIDEOS_DIR / "ai_generated" # video từ fal.ai
AUDIO_DIR     = VIDEOS_DIR / "audio"        # voiceover mp3
FINAL_DIR     = VIDEOS_DIR / "final"        # video ghép xong

for d in [RAW_DIR, AI_VIDEO_DIR, AUDIO_DIR, FINAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SCRIPTS_JSON   = DATA_DIR / "scripts_output.json"
PRODUCTS_CSV   = DATA_DIR / "products.csv"
VIDEOS_JSON    = DATA_DIR / "videos_ready.json"

# ── API Keys ──────────────────────────────────────────────────────────────────
FAL_API_KEY        = os.getenv("FAL_API_KEY")           # fal.ai
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID           = os.getenv("VOICE_ID", "")          # ElevenLabs Voice ID tiếng Việt

# ── fal.ai Kling config ───────────────────────────────────────────────────────
# Standard 5s ≈ $0.054 | Pro 5s ≈ $0.14
KLING_MODEL    = "fal-ai/kling-video/v1/standard/image-to-video"
KLING_DURATION = "5"       # giây: "5" hoặc "10"
KLING_RATIO    = "9:16"    # TikTok dọc


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 1 — Tải ảnh sản phẩm
# ════════════════════════════════════════════════════════════════════════════

def download_product_image(product_id: str, image_url: str) -> Path | None:
    """Tải ảnh sản phẩm về máy."""
    if not image_url:
        log.warning(f"  ⚠️  Không có image_url cho {product_id}")
        return None

    ext      = Path(image_url.split("?")[0]).suffix or ".jpg"
    out_path = RAW_DIR / f"{product_id}{ext}"

    if out_path.exists():
        log.info(f"  📁 Ảnh đã có sẵn: {out_path.name}")
        return out_path

    try:
        resp = requests.get(image_url, timeout=20,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        log.info(f"  ✅ Tải ảnh xong: {out_path.name}")
        return out_path
    except Exception as e:
        log.error(f"  ❌ Lỗi tải ảnh: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 2 — Tạo video từ ảnh bằng fal.ai Kling
# ════════════════════════════════════════════════════════════════════════════

def image_to_video_kling(product_id: str, image_path: Path, prompt: str) -> Path | None:
    """
    Gửi ảnh lên fal.ai → Kling image-to-video.
    Trả về đường dẫn file .mp4 đã tải về.
    """
    if not FAL_API_KEY:
        log.error("❌ FAL_API_KEY chưa được set trong .env")
        return None

    out_path = AI_VIDEO_DIR / f"{product_id}.mp4"
    if out_path.exists():
        log.info(f"  📁 Video AI đã có: {out_path.name}")
        return out_path

    log.info(f"  🎬 Đang tạo video AI (Kling)...")

    # Encode ảnh sang base64 data URI
    mime = "image/jpeg" if image_path.suffix.lower() in [".jpg",".jpeg"] else "image/png"
    b64  = base64.b64encode(image_path.read_bytes()).decode()
    image_data_uri = f"data:{mime};base64,{b64}"

    headers = {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "image_url":  image_data_uri,
        "prompt":     prompt,
        "duration":   KLING_DURATION,
        "aspect_ratio": KLING_RATIO,
    }

    # ── Submit job ────────────────────────────────────────────────────────
    submit_url = f"https://queue.fal.run/{KLING_MODEL}"
    try:
        resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data     = resp.json()
        request_id = data.get("request_id")
        if not request_id:
            log.error(f"  ❌ Không có request_id: {data}")
            return None
        log.info(f"  ⏳ Job submitted | request_id: {request_id}")
    except Exception as e:
        log.error(f"  ❌ Lỗi submit Kling: {e}")
        return None

    # ── Poll kết quả (tối đa 5 phút) ─────────────────────────────────────
    status_url = f"https://queue.fal.run/{KLING_MODEL}/requests/{request_id}/status"
    result_url = f"https://queue.fal.run/{KLING_MODEL}/requests/{request_id}"
    deadline   = time.time() + 300  # 5 phút

    while time.time() < deadline:
        time.sleep(8)
        try:
            sr   = requests.get(status_url, headers=headers, timeout=15)
            status = sr.json().get("status", "")
            log.info(f"  ... status: {status}")

            if status == "COMPLETED":
                break
            elif status in ("FAILED", "CANCELLED"):
                log.error(f"  ❌ Job {status}")
                return None
        except Exception:
            pass
    else:
        log.error("  ❌ Timeout chờ Kling")
        return None

    # ── Lấy URL video ─────────────────────────────────────────────────────
    try:
        rr        = requests.get(result_url, headers=headers, timeout=15)
        result    = rr.json()
        video_url = (result.get("video") or {}).get("url") or \
                    (result.get("output") or {}).get("video", {}).get("url", "")
        if not video_url:
            # Thử flatten output
            for key in ["video_url", "url"]:
                video_url = result.get(key, "")
                if video_url:
                    break
        if not video_url:
            log.error(f"  ❌ Không tìm thấy video URL trong kết quả: {result}")
            return None
    except Exception as e:
        log.error(f"  ❌ Lỗi lấy kết quả: {e}")
        return None

    # ── Tải video về ──────────────────────────────────────────────────────
    try:
        vr = requests.get(video_url, timeout=60)
        vr.raise_for_status()
        out_path.write_bytes(vr.content)
        log.info(f"  ✅ Video AI xong: {out_path.name}")
        return out_path
    except Exception as e:
        log.error(f"  ❌ Lỗi tải video: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 3 — Tạo voiceover bằng ElevenLabs
# ════════════════════════════════════════════════════════════════════════════

def generate_voiceover(product_id: str, script_text: str) -> Path | None:
    """Gọi ElevenLabs TTS → lưu file mp3."""
    if not ELEVENLABS_API_KEY:
        log.error("❌ ELEVENLABS_API_KEY chưa set")
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
            "stability":        0.5,
            "similarity_boost": 0.75,
            "style":            0.3,
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
        log.error(f"  ❌ Lỗi ElevenLabs: {e} | {getattr(e.response,'text','') if hasattr(e,'response') else ''}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 4 — Ghép audio vào video bằng FFmpeg
# ════════════════════════════════════════════════════════════════════════════

def merge_audio_video(product_id: str, video_path: Path, audio_path: Path) -> Path | None:
    """
    FFmpeg: ghép voiceover vào video AI.
    - Nếu audio dài hơn video → loop video cho đủ độ dài audio
    - Output: 9:16, H.264, AAC, tối đa 60 giây (TikTok limit)
    """
    out_path = FINAL_DIR / f"{product_id}_final.mp4"
    if out_path.exists():
        log.info(f"  📁 Video final đã có: {out_path.name}")
        return out_path

    log.info("  🔧 Ghép audio + video (FFmpeg)...")

    # Lấy độ dài audio để loop video cho vừa
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    try:
        audio_duration = float(
            subprocess.check_output(probe_cmd, stderr=subprocess.DEVNULL).decode().strip()
        )
    except Exception:
        audio_duration = 30.0  # fallback

    # Giới hạn 60 giây cho TikTok
    target_duration = min(audio_duration, 60.0)
    log.info(f"  ⏱️  Thời lượng video: {target_duration:.1f}s")

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",        # loop video nếu cần
        "-i", str(video_path),       # input video (looped)
        "-i", str(audio_path),       # input audio
        "-t", str(target_duration),  # cắt đúng độ dài
        # Scale về 1080x1920 (TikTok 9:16)
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_path)
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            log.error(f"  ❌ FFmpeg lỗi:\n{result.stderr[-500:]}")
            return None
        log.info(f"  ✅ Video final: {out_path.name}")
        return out_path
    except subprocess.TimeoutExpired:
        log.error("  ❌ FFmpeg timeout")
        return None
    except FileNotFoundError:
        log.error("  ❌ FFmpeg chưa được cài. Tải tại: https://ffmpeg.org/download.html")
        return None


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 5 — Tạo video prompt cho Kling từ script
# ════════════════════════════════════════════════════════════════════════════

def build_kling_prompt(product_name: str, script_text: str) -> str:
    """
    Tạo prompt ngắn gọn cho Kling image-to-video.
    Kling hoạt động tốt nhất với prompt tiếng Anh, mô tả chuyển động.
    """
    # Lấy 1-2 keywords từ tên sản phẩm
    name_short = product_name[:40] if product_name else "fashion product"

    prompt = (
        f"Product showcase video of {name_short}. "
        "Smooth slow rotation, cinematic lighting, "
        "soft bokeh background, professional product photography style, "
        "elegant motion, 4K quality, TikTok vertical format."
    )
    return prompt


# ════════════════════════════════════════════════════════════════════════════
# MAIN — Xử lý tất cả sản phẩm trong scripts_output.json
# ════════════════════════════════════════════════════════════════════════════

def load_scripts() -> list[dict]:
    if not SCRIPTS_JSON.exists():
        log.error(f"❌ Không tìm thấy {SCRIPTS_JSON} — chạy generate_scripts.py trước.")
        return []
    with open(SCRIPTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_products() -> dict:
    """Load products.csv thành dict theo product_id."""
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
    log.info("  Luồng: ảnh sản phẩm → Kling AI video → voiceover → ghép")
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
        image_path = None
        if image_url:
            image_path = download_product_image(pid, image_url)
        else:
            log.warning("  ⚠️  Không có image_url — bỏ qua bước tạo video AI")

        # ── 2. Tạo video AI từ ảnh ───────────────────────────────────────
        ai_video_path = None
        if image_path:
            kling_prompt  = build_kling_prompt(product_name, script_text)
            ai_video_path = image_to_video_kling(pid, image_path, kling_prompt)
        else:
            log.warning("  ⚠️  Không có ảnh — không tạo được video AI")
            continue

        if not ai_video_path:
            log.warning("  ⚠️  Tạo video AI thất bại — bỏ qua sản phẩm này")
            continue

        # ── 3. Tạo voiceover ─────────────────────────────────────────────
        audio_path = generate_voiceover(pid, script_text)
        if not audio_path:
            log.warning("  ⚠️  Voiceover thất bại — bỏ qua")
            continue

        # ── 4. Ghép video + audio ────────────────────────────────────────
        final_path = merge_audio_video(pid, ai_video_path, audio_path)
        if not final_path:
            log.warning("  ⚠️  Ghép video thất bại — bỏ qua")
            continue

        # ── 5. Ghi vào danh sách sẵn sàng đăng ─────────────────────────
        videos_ready.append({
            "product_id":    pid,
            "product_name":  product_name,
            "video_path":    str(final_path),
            "affiliate_link": products.get(pid, {}).get("affiliate_link", ""),
            "script":        script_text,
            "created_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status":        "ready",
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