import anthropic
import pandas as pd
import json
import os
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def viet_script(ten_sp, gia, tinh_nang, hoa_hong):
    prompt = f"""Bạn là chuyên gia viết script TikTok affiliate viral.

Viết script video TikTok 45 giây cho sản phẩm sau:
- Tên: {ten_sp}
- Giá: {gia}
- Tính năng nổi bật: {tinh_nang}
- Hoa hồng affiliate: {hoa_hong}%

Cấu trúc BẮT BUỘC:
1. Hook (3 giây): Câu gây tò mò, KHÔNG bắt đầu bằng "Bạn có biết"
2. Vấn đề (5 giây): Vấn đề người dùng đang gặp
3. Giải pháp (20 giây): 2-3 lợi ích cụ thể
4. Bằng chứng (10 giây): 1 chi tiết thực tế
5. CTA (7 giây): Kêu gọi mua, nhắc link trong bio

Yêu cầu:
- Tổng 90-110 từ tiếng Việt
- Giọng tự nhiên như người thật nói
- KHÔNG dùng: "tuyệt vời", "siêu phẩm", "đỉnh cao"
- Chỉ trả về script, không giải thích"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

def xu_ly_danh_sach(file_csv):
    df = pd.read_csv(file_csv)
    ket_qua = []

    for i, row in df.iterrows():
        print(f"Đang viết script {i+1}/{len(df)}: {row['product_name']}")
        script = viet_script(
            ten_sp=row['product_name'],
            gia=row['price'],
            tinh_nang=row.get('features', 'Tiện dụng, chất lượng cao'),
            hoa_hong=row['commission_rate']
        )
        ket_qua.append({
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'affiliate_link': row['affiliate_link'],
            'price': row['price'],
            'script': script
        })
        print(f"✓ Xong: {row['product_name']}\n")

    output_file = os.path.join(base_dir, 'data', 'scripts_output.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ket_qua, f, ensure_ascii=False, indent=2)

    print(f"Hoàn thành! Đã tạo {len(ket_qua)} scripts → {output_file}")
    return ket_qua

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, 'data', 'products.csv')
    xu_ly_danh_sach(csv_path)