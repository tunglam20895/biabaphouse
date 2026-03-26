# TikTok Affiliate Pipeline — Context Document

> Paste file này vào đầu mỗi cuộc hội thoại mới với AI để không cần mô tả lại từ đầu.

---

## Mục tiêu dự án

Xây dựng pipeline **tự động hoàn toàn** để làm TikTok Affiliate:
1. Tự động lấy sản phẩm trending từ TikTok Affiliate Market (Selenium + Edge)
2. Tự động viết script quảng cáo bằng Claude AI
3. Tự động download video gốc từ TikTok (yt-dlp + cookies Chrome)
4. Tự động tạo voiceover tiếng Việt bằng ElevenLabs
5. Tự động ghép audio vào video bằng FFmpeg
6. Tự động đăng lên TikTok qua Blotato
7. Tự động lên lịch chạy hàng ngày lúc 7:00 qua Windows Task Scheduler

---

## Môi trường & công cụ

- **OS:** Windows
- **Python:** 3.11
- **IDE:** PyCharm
- **Browser:** Microsoft Edge (profile đã đăng nhập TikTok sẵn)
- **Scheduler:** Windows Task Scheduler (file `setup_scheduler.ps1`)

---

## Cấu trúc thư mục

```
G:\TIKTOK\
├── scripts\
│   ├── generate_scripts.py     # Bước 2: Viết script bằng Claude AI
│   ├── create_videos.py        # Bước 3-5: Download + voiceover + ghép video
│   ├── schedule_posts.py       # Bước 6: Đăng lên TikTok qua Blotato
│   └── fetch_products.py       # Bước 1: Lấy sản phẩm từ TikTok Affiliate
├── data\
│   ├── products.csv            # Danh sách sản phẩm affiliate
│   ├── scripts_output.json     # Script đã tạo bởi Claude AI
│   ├── videos_ready.json       # Danh sách video sẵn sàng đăng
│   └── fetch_log.txt           # Log của fetch_products.py
├── videos\                     # Chứa video gốc, audio, video final
├── .env                        # API keys
├── .venv\                      # Virtual environment
├── run_pipeline.py             # File chạy chính — menu chọn chế độ
├── setup_scheduler.ps1         # Tạo Windows Task Scheduler tự động
└── guilde.md                   # File context này
```

---

## Các file quan trọng

### `data/products.csv` — cấu trúc cột:
```
product_id, product_name, price, features, commission_rate, affiliate_link, video_url, fetched_at
```
- `affiliate_link`: link affiliate để kiếm hoa hồng
- `video_url`: link video TikTok của seller để download
- `fetched_at`: thời điểm lấy dữ liệu

### `.env` — các biến môi trường:
```
ANTHROPIC_API_KEY=...
BLOTATO_API_KEY=...
ELEVENLABS_API_KEY=...
VOICE_ID=...           ← Voice ID tiếng Việt từ ElevenLabs (chưa điền)
EDGE_USER_DATA=...     ← tuỳ chọn, mặc định tự detect theo USERNAME
EDGE_PROFILE=Default   ← tuỳ chọn
```

---

## API & Services đang dùng

| Service | Dùng để | Ghi chú |
|---|---|---|
| **Anthropic Claude** | Viết script quảng cáo | Model: `claude-sonnet-4-6` |
| **ElevenLabs** | Tạo voiceover tiếng Việt | Model: `eleven_multilingual_v2` |
| **Blotato** | Đăng video lên TikTok | Header: `blotato-api-key` |
| **yt-dlp** | Download video TikTok | CLI, dùng `--cookies-from-browser chrome` |
| **FFmpeg** | Ghép audio vào video | CLI |
| **Selenium + Edge** | Crawl TikTok Affiliate Market | Dùng Edge profile thật |

### Blotato — chi tiết quan trọng:
- Base URL: `backend.blotato.com/v2` (KHÔNG phải `api.blotato.com`)
- Header xác thực: `blotato-api-key: YOUR_KEY` (không dùng Bearer)
- TikTok account ID: `34757` (username: `tunglam358`)
- Lấy danh sách accounts: `GET /v2/users/me/accounts` → parse `response["items"]`
- Đăng bài: `POST /v2/posts`

### ElevenLabs — chi tiết:
- Endpoint: `api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}`
- Model: `eleven_multilingual_v2`
- Voice ID: lấy từ `.env` → biến `VOICE_ID` (chưa điền)

### Selenium + Edge — chi tiết:
- Dùng `webdriver_manager` để tự tải EdgeDriver
- User data: `C:\Users\{USERNAME}\AppData\Local\Microsoft\Edge\User Data`
- Profile: `Default` (hoặc `Profile 1`)
- Ẩn automation: `excludeSwitches: ["enable-automation"]`
- **Lưu ý:** Phải đóng Edge hoàn toàn trước khi chạy Selenium

---

## `run_pipeline.py` — menu chính:

```
1 - Chạy toàn bộ (fetch → script → video → đăng)
2 - Bỏ qua bước 1 (đã có script, chạy từ video)
3 - Chỉ tạo video (không đăng)
4 - Chỉ đăng bài (đã có video sẵn)
5 - Chỉ tạo script
6 - Thêm sản phẩm mới vào CSV
```

Chạy tự động không cần menu (dùng cho Task Scheduler):
```bash
python run_pipeline.py --auto
```

---

## `setup_scheduler.ps1` — Windows Task Scheduler:

- Tạo task chạy `run_pipeline.py --auto` mỗi ngày lúc **07:00**
- Tên task: `TikTok_Affiliate_Pipeline`
- Cách chạy: chuột phải file → "Run with PowerShell"
- Giới hạn thời gian chạy: 2 giờ, tự retry 2 lần nếu lỗi
- **Lưu ý quan trọng:** Phải đóng Edge hoàn toàn trước 07:00 mỗi ngày

---

## `fetch_products.py` — logic crawl:

1. Mở Edge với profile thật → vào `affiliate.tiktok.com/connection/creator?tab=top_products`
2. Lọc theo Category (mặc định: `Fashion`)
3. Sort theo Commission % cao nhất
4. Scrape Top 5 sản phẩm (tên, giá, commission)
5. Vào từng trang chi tiết → lấy affiliate link + video URL
6. Ghi vào `data/products.csv` (merge với data cũ, không ghi đè)

---

## Trạng thái hiện tại

- [x] `fetch_products.py` — đã tạo đầy đủ, dùng Edge Selenium
- [x] `generate_scripts.py` — hoạt động tốt
- [x] `schedule_posts.py` — kết nối Blotato OK, tìm được TikTok account
- [x] `create_videos.py` — đã tạo, chưa test với link thật
- [x] `run_pipeline.py` — menu hoạt động, hỗ trợ `--auto`
- [x] `setup_scheduler.ps1` — tạo Task Scheduler Windows
- [ ] **Cần làm tiếp**: Điền `VOICE_ID` tiếng Việt vào `.env`
- [ ] **Cần làm tiếp**: Cập nhật `products.csv` với link sản phẩm thật
- [ ] **Cần làm tiếp**: Test toàn bộ pipeline end-to-end
- [ ] **Cần làm tiếp**: Chạy `setup_scheduler.ps1` để bật auto-run

---

## Vấn đề đã gặp & cách fix

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `api.blotato.com` không tồn tại | Sai endpoint | Dùng `backend.blotato.com/v2` |
| Không tìm thấy TikTok account | API trả `items[]` không phải list | Dùng `accounts.get("items", [])` |
| TikTok block IP khi download | Không có authentication | Thêm `--cookies-from-browser chrome` vào yt-dlp |
| `create_videos.py` không tìm thấy | File để nhầm thư mục `videos/` | Move sang thư mục `scripts/` |
| 2 hàm `download_video_tiktok` trùng | Copy paste nhầm | Xóa hàm cũ, giữ hàm mới có cookies |
| Edge bị chiếm bởi Selenium | Edge đang mở sẵn | Đóng Edge hoàn toàn trước khi chạy |

---

## Thông tin tài khoản

- **TikTok**: `tunglam358` (ID: `34757`) — đang chờ duyệt Affiliate
- **Shop TikTok**: Biabaphouse (Seller Center) — tài khoản seller riêng
- **Mục tiêu**: Làm affiliate sản phẩm của người khác để kiếm hoa hồng

---

## Bước tiếp theo (theo thứ tự ưu tiên)

1. **Điền `VOICE_ID`** tiếng Việt vào `.env`:
   - Vào `elevenlabs.io` → Voices → tìm giọng Việt → copy Voice ID
   - Hoặc dùng API: `GET https://api.elevenlabs.io/v1/voices` để liệt kê

2. **Đợi TikTok duyệt Affiliate** → sau đó vào `affiliate.tiktok.com` tìm sản phẩm

3. **Test `fetch_products.py`**:
   - Đóng Edge hoàn toàn
   - Chạy: `python scripts/fetch_products.py`
   - Kiểm tra `data/products.csv` có dữ liệu không

4. **Test toàn bộ pipeline**:
   - Chạy: `python run_pipeline.py` → chọn **1** (toàn bộ)
   - Hoặc chạy từng bước: 5 → 3 → 4

5. **Bật auto-run**:
   - Chuột phải `setup_scheduler.ps1` → Run with PowerShell
   - Kiểm tra trong Task Scheduler: `Win + R` → `taskschd.msc`