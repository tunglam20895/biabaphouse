"""
PIPELINE TIKTOK AFFILIATE - CHẠY TỰ ĐỘNG HOÀN TOÀN
Chỉ cần chạy file này, hệ thống tự lo hết!
"""
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def chay_buoc(ten_buoc, script_path):
    print(f"\n{'='*50}")
    print(f"ĐANG CHẠY: {ten_buoc}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=False
    )
    if result.returncode != 0:
        print(f"✗ Lỗi ở bước: {ten_buoc}")
        return False
    return True

def scripts_da_co():
    """Kiểm tra file scripts_output.json đã tồn tại và có dữ liệu chưa"""
    scripts_file = os.path.join(BASE_DIR, 'data', 'scripts_output.json')
    if not os.path.exists(scripts_file):
        return False
    import json
    with open(scripts_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return len(data) > 0

def chon_che_do():
    print("\n" + "="*50)
    print("  TIKTOK AFFILIATE PIPELINE")
    print("="*50)
    print("\nChọn chế độ chạy:")
    print("  1 - Chạy toàn bộ (tạo script → video → đăng)")
    print("  2 - Bỏ qua bước 1 (đã có script rồi, chạy từ video)")
    print("  3 - Chỉ tạo video (không đăng)")
    print("  4 - Chỉ đăng bài (đã có video sẵn)")
    print("  5 - Chỉ tạo script")
    print("  6 - Thêm sản phẩm mới vào CSV")
    print()

    while True:
        chon = input("Nhập số (1-6): ").strip()
        if chon in ['1', '2', '3', '4', '5', '6']:
            return chon
        print("Vui lòng nhập số từ 1 đến 6!")

if __name__ == "__main__":
    # Tự động gợi ý nếu đã có script
    if scripts_da_co():
        print("\n✓ Phát hiện scripts_output.json đã có dữ liệu!")
        print("  → Có thể bỏ qua Bước 1 để tiết kiệm thời gian và API credits")

    che_do = chon_che_do()

    if che_do == '1':
        # Toàn bộ pipeline
        if not chay_buoc("Bước 1: Viết script bằng Claude AI",
                         os.path.join(BASE_DIR, 'scripts', 'generate_scripts.py')): exit(1)
        if not chay_buoc("Bước 2: Download video + Tạo voiceover + Ghép video",
                         os.path.join(BASE_DIR, 'scripts', 'create_videos.py')): exit(1)
        if not chay_buoc("Bước 3: Đăng lên TikTok",
                         os.path.join(BASE_DIR, 'scripts', 'schedule_posts.py')): exit(1)

    elif che_do == '2':
        # Đã có script, chạy từ bước 2
        if not scripts_da_co():
            print("✗ Chưa có scripts_output.json! Hãy chạy chế độ 1 trước.")
            exit(1)
        if not chay_buoc("Bước 2: Download video + Tạo voiceover + Ghép video",
                         os.path.join(BASE_DIR, 'scripts', 'create_videos.py')): exit(1)
        if not chay_buoc("Bước 3: Đăng lên TikTok",
                         os.path.join(BASE_DIR, 'scripts', 'schedule_posts.py')): exit(1)

    elif che_do == '3':
        # Chỉ tạo video
        if not scripts_da_co():
            print("✗ Chưa có scripts_output.json! Hãy chạy chế độ 1 hoặc 5 trước.")
            exit(1)
        if not chay_buoc("Bước 2: Download video + Tạo voiceover + Ghép video",
                         os.path.join(BASE_DIR, 'scripts', 'create_videos.py')): exit(1)

    elif che_do == '4':
        # Chỉ đăng bài
        videos_file = os.path.join(BASE_DIR, 'data', 'videos_ready.json')
        if not os.path.exists(videos_file):
            print("✗ Chưa có videos_ready.json! Hãy tạo video trước.")
            exit(1)
        if not chay_buoc("Bước 3: Đăng lên TikTok",
                         os.path.join(BASE_DIR, 'scripts', 'schedule_posts.py')): exit(1)

    elif che_do == '5':
        # Chỉ tạo script
        if not chay_buoc("Bước 1: Viết script bằng Claude AI",
                         os.path.join(BASE_DIR, 'scripts', 'generate_scripts.py')): exit(1)

    elif che_do == '6':
        chay_buoc("Thêm sản phẩm mới",
                  os.path.join(BASE_DIR, 'scripts', 'fetch_products.py'))

    print(f"\n{'='*50}")
    print("PIPELINE HOÀN THÀNH!")
    print(f"{'='*50}")