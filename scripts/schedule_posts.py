import json
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BLOTATO_API_KEY = os.getenv("BLOTATO_API_KEY")
BASE_URL = "https://backend.blotato.com/v2"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEADERS = {
    "blotato-api-key": BLOTATO_API_KEY,
    "Content-Type": "application/json"
}


def get_tiktok_account_id():
    """Lấy ID tài khoản TikTok đã kết nối trong Blotato"""
    resp = requests.get(
        f"{BASE_URL}/users/me/accounts",
        headers=HEADERS
    )
    print(f"Status: {resp.status_code}")
    accounts = resp.json()
    print(f"Accounts: {json.dumps(accounts, indent=2)}")

    # Tìm tài khoản TikTok
    items = accounts.get("items", [])
    for acc in items:
        platform = acc.get("platform", "").lower()
        if "tiktok" in platform:
            print(f"✓ Tìm thấy TikTok: {acc.get('name')} (ID: {acc['id']})")
            return acc["id"]

    print("✗ Không tìm thấy tài khoản TikTok!")
    return None


def dang_video_ngay(account_id, video_url, caption):
    """Đăng video lên TikTok ngay lập tức"""
    payload = {
        "post": {
            "accountId": str(account_id),
            "content": {
                "text": caption,
                "mediaUrls": [video_url]
            },
            "platform": "tiktok"
        },
        "target": {
            "targetType": "tiktok"
        }
    }
    resp = requests.post(
        f"{BASE_URL}/posts",
        headers=HEADERS,
        json=payload
    )
    result = resp.json()
    if resp.status_code == 200:
        print(f"✓ Đăng thành công!")
        return True
    else:
        print(f"✗ Lỗi: {result}")
        return False


def len_lich_dang(account_id, video_url, caption, gio_dang):
    """Lên lịch đăng video lên TikTok"""
    payload = {
        "post": {
            "accountId": str(account_id),
            "content": {
                "text": caption,
                "mediaUrls": [video_url]
            },
            "platform": "tiktok"
        },
        "target": {
            "targetType": "tiktok"
        },
        "scheduleDate": gio_dang.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    }
    resp = requests.post(
        f"{BASE_URL}/posts",
        headers=HEADERS,
        json=payload
    )
    result = resp.json()
    if resp.status_code == 200:
        print(f"✓ Lên lịch: {gio_dang.strftime('%d/%m %H:%M')}")
        return True
    else:
        print(f"✗ Lỗi: {result}")
        return False


def tinh_gio_dang(so_video):
    """3 video/ngày lúc 8h, 12h, 19h"""
    gio_cao_diem = [8, 12, 19]
    lich = []
    ngay = datetime.now().replace(minute=0, second=0, microsecond=0)
    if ngay.hour >= 19:
        ngay += timedelta(days=1)

    i = 0
    while i < so_video:
        for gio in gio_cao_diem:
            if i >= so_video:
                break
            lich.append(ngay.replace(hour=gio))
            i += 1
        ngay += timedelta(days=1)
    return lich

def dang_ngay(account_id, video_url, caption):
    """Đăng video lên TikTok ngay lập tức không cần lên lịch"""
    payload = {
        "post": {
            "accountId": str(account_id),
            "content": {
                "text": caption,
                "mediaUrls": [video_url]
            },
            "platform": "tiktok"
        },
        "target": {
            "targetType": "tiktok"
        }
    }
    resp = requests.post(
        f"{BASE_URL}/posts",
        headers=HEADERS,
        json=payload
    )
    if resp.status_code == 200:
        print(f"✓ Đã đăng ngay!")
        return True
    else:
        print(f"✗ Lỗi: {resp.text}")
        return False

def xu_ly_dang_bai(dang_ngay_luon=False):
    account_id = get_tiktok_account_id()
    if not account_id:
        return

    videos_file = os.path.join(BASE_DIR, 'data', 'videos_ready.json')
    if not os.path.exists(videos_file):
        print("Chưa có file videos_ready.json!")
        return

    with open(videos_file, 'r', encoding='utf-8') as f:
        videos = json.load(f)

    lich_dang = tinh_gio_dang(len(videos))
    thanh_cong = 0

    for video, gio in zip(videos, lich_dang):
        print(f"\nXử lý: {video['product_name']}")
        caption = (
            f"{video['product_name']} 🛒\n"
            f"Link mua trong bio!\n"
            f"#tiktokshop #review #muahang #trending"
        )
        video_url = video.get("video_url", "")
        if not video_url:
            print(f"✗ Thiếu video_url")
            continue

        if dang_ngay_luon:
            # Đăng ngay không cần lên lịch
            if dang_ngay(account_id, video_url, caption):
                thanh_cong += 1
        else:
            # Lên lịch theo giờ cao điểm
            if len_lich_dang(account_id, video_url, caption, gio):
                thanh_cong += 1

    print(f"\nHoàn thành! {thanh_cong}/{len(videos)} video!")

if __name__ == "__main__":
    # Đổi thành True nếu muốn đăng ngay
    xu_ly_dang_bai(dang_ngay_luon=False)
