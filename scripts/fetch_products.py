"""
fetch_products.py
─────────────────
Tự động lấy Top 5 sản phẩm Thời trang có commission % cao nhất
từ TikTok Affiliate Market → ghi vào data/products.csv
Dùng Microsoft Edge (profile đã đăng nhập sẵn)

Cách dùng:
  python scripts/fetch_products.py
"""

import os, csv, time, random, re, logging, sys
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException
)
from dotenv import load_dotenv

load_dotenv()

# ── Đường dẫn msedgedriver ───────────────────────────────────────────────────
# Đã tải về và đặt tại G:\TIKTOK\msedgedriver.exe
EDGE_DRIVER_PATH = r"G:\TIKTOK\msedgedriver.exe"

# ── Cấu hình ────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent        # G:\TIKTOK\
DATA_DIR     = BASE_DIR / "data"
PRODUCTS_CSV = DATA_DIR / "products.csv"
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DATA_DIR / "fetch_log.txt", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# ── Tham số crawl ────────────────────────────────────────────────────────────
TOP_N      = 1
CATEGORY   = "Fashion"
TOP_PRODUCTS_URL = (
    "https://affiliate.tiktok.com/connection/creator"
    "?shop_region=VN&tab=top_products"
)

# ── Edge profile ─────────────────────────────────────────────────────────────
EDGE_USER_DATA = os.getenv(
    "EDGE_USER_DATA",
    rf"C:\Users\{os.environ.get('USERNAME','User')}\AppData\Local\Microsoft\Edge\User Data"
)
EDGE_PROFILE = os.getenv("EDGE_PROFILE", "Default")

CSV_COLUMNS = [
    "product_id", "product_name", "price", "features",
    "commission_rate", "affiliate_link", "video_url", "fetched_at"
]


# ════════════════════════════════════════════════════════════════════════════
# DRIVER — Microsoft Edge
# ════════════════════════════════════════════════════════════════════════════

def create_driver() -> webdriver.Edge:
    opts = Options()

    # Dùng profile Edge thật → đã đăng nhập TikTok
    opts.add_argument(f"--user-data-dir={EDGE_USER_DATA}")
    opts.add_argument(f"--profile-directory={EDGE_PROFILE}")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    if not os.path.exists(EDGE_DRIVER_PATH):
        raise FileNotFoundError(
            f"Không tìm thấy msedgedriver tại: {EDGE_DRIVER_PATH}\n"
            f"→ Tải tại: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/\n"
            f"→ Giải nén rồi copy msedgedriver.exe vào G:\\TIKTOK\\"
        )

    service = Service(EDGE_DRIVER_PATH)
    driver  = webdriver.Edge(service=service, options=opts)

    # Ẩn dấu hiệu automation
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def wait_for(driver, by, sel, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, sel))
    )


def wait_clickable(driver, by, sel, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, sel))
    )


def pause(a=0.8, b=2.0):
    time.sleep(random.uniform(a, b))


def safe_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    pause(0.2, 0.5)
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 1 — Mở trang + lọc Category + sort Commission
# ════════════════════════════════════════════════════════════════════════════

def open_and_setup(driver):
    log.info("🌐 Mở trang Top Products (Edge)...")
    driver.get(TOP_PRODUCTS_URL)
    pause(3, 5)

    if "login" in driver.current_url.lower():
        raise RuntimeError(
            "Chưa đăng nhập TikTok trên Edge.\n"
            "→ Đóng Edge hoàn toàn → mở lại → đăng nhập affiliate.tiktok.com\n"
            "→ Đóng Edge → chạy lại script."
        )

    log.info("✅ Đã vào trang. Đang lọc danh mục...")
    _apply_category(driver)
    _sort_by_commission(driver)
    pause(2, 3)


def _apply_category(driver):
    cat_xpaths = [
        "//button[contains(.,'Category')]",
        "//span[contains(.,'Category')]/ancestor::button",
        "//div[@role='button'][contains(.,'Category')]",
    ]
    btn = None
    for xp in cat_xpaths:
        try:
            btn = wait_clickable(driver, By.XPATH, xp, timeout=8)
            break
        except TimeoutException:
            continue

    if not btn:
        log.warning("⚠️  Không tìm thấy bộ lọc Category — bỏ qua.")
        return

    safe_click(driver, btn)
    pause(0.8, 1.5)

    opt_xpaths = [
        f"//li[contains(.,'{CATEGORY}')]",
        f"//div[@role='option'][contains(.,'{CATEGORY}')]",
        f"//label[contains(.,'{CATEGORY}')]",
        "//li[contains(.,'Thời trang')]",
        "//div[contains(.,'Thời trang')][@role='option']",
    ]
    for xp in opt_xpaths:
        try:
            opt = driver.find_element(By.XPATH, xp)
            safe_click(driver, opt)
            pause(0.5, 1)
            log.info(f"✅ Đã chọn danh mục: {CATEGORY}")
            break
        except NoSuchElementException:
            continue

    for xp in ["//button[contains(.,'Apply')]", "//button[contains(.,'Confirm')]", "//button[contains(.,'OK')]"]:
        try:
            safe_click(driver, driver.find_element(By.XPATH, xp))
            pause(1.5, 2.5)
            break
        except NoSuchElementException:
            continue


def _sort_by_commission(driver):
    sort_xpaths = [
        "//th[contains(.,'Commission')]",
        "//span[contains(.,'Commission')]/ancestor::th",
        "//div[contains(.,'Commission Rate')][@role='button']",
        "//button[contains(.,'Commission')]",
    ]
    for xp in sort_xpaths:
        try:
            el = wait_clickable(driver, By.XPATH, xp, timeout=8)
            safe_click(driver, el)
            pause(1.5, 2)
            log.info("✅ Đã sort theo Commission %")
            return
        except TimeoutException:
            continue
    log.warning("⚠️  Không sort được theo Commission.")


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 2 — Scrape danh sách sản phẩm
# ════════════════════════════════════════════════════════════════════════════

def scrape_top_products(driver) -> list[dict]:
    log.info(f"📋 Scraping Top {TOP_N} sản phẩm...")

    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 700)")
        pause(0.4, 0.7)
    driver.execute_script("window.scrollTo(0, 0)")
    pause(0.8, 1.2)

    row_selectors = [
        "tr[class*='product']",
        "div[class*='product-item']",
        "div[class*='ProductItem']",
        "li[class*='product']",
        "[data-testid='product-row']",
        "tbody tr",
    ]

    rows = []
    for sel in row_selectors:
        rows = driver.find_elements(By.CSS_SELECTOR, sel)
        if rows:
            log.info(f"  → {len(rows)} rows | selector: {sel}")
            break

    if not rows:
        log.warning("⚠️  Fallback: parse page source")
        return _parse_from_source(driver)

    products = []
    for row in rows[:TOP_N]:
        p = _parse_row(row)
        if p:
            products.append(p)

    log.info(f"✅ Parse xong {len(products)} sản phẩm.")
    return products


def _parse_row(row) -> dict | None:
    p = {}

    for sel in ["[class*='name']","[class*='title']","td:nth-child(2)","h3","h4"]:
        try:
            txt = row.find_element(By.CSS_SELECTOR, sel).text.strip()
            if txt and len(txt) > 3:
                p["product_name"] = txt
                break
        except NoSuchElementException:
            continue
    if not p.get("product_name"):
        return None

    p["price"] = "0"
    for sel in ["[class*='price']","[class*='Price']","td:nth-child(3)"]:
        try:
            txt = row.find_element(By.CSS_SELECTOR, sel).text.strip()
            v   = re.sub(r"[^\d,.]", "", txt)
            if v:
                p["price"] = v
                break
        except NoSuchElementException:
            continue

    p["commission_rate"] = ""
    for sel in ["[class*='commission']","[class*='Commission']","td:nth-child(4)"]:
        try:
            txt = row.find_element(By.CSS_SELECTOR, sel).text.strip()
            m   = re.search(r"[\d.]+\s*%", txt)
            if m:
                p["commission_rate"] = m.group().replace(" ", "")
                break
        except NoSuchElementException:
            continue

    p["product_id"]  = f"p{int(time.time())}{random.randint(100,999)}"
    p["_detail_url"] = ""
    try:
        a    = row.find_element(By.CSS_SELECTOR, "a[href]")
        href = a.get_attribute("href") or ""
        m    = re.search(r"product[_/]?id[=/](\d+)|/product/(\d+)", href, re.I)
        if m:
            p["product_id"] = m.group(1) or m.group(2)
        p["_detail_url"] = href
    except NoSuchElementException:
        pass

    p.update({
        "features": "", "affiliate_link": "", "video_url": "",
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    return p


def _parse_from_source(driver) -> list[dict]:
    src    = driver.page_source
    names  = re.findall(r'"(?:product_name|name)"\s*:\s*"([^"]{4,})"', src)
    comms  = re.findall(r'"commission[^"]*"\s*:\s*"?([\d.]+%?)"?', src)
    prices = re.findall(r'"price"\s*:\s*"?(\d[\d,.]+)"?', src)
    ids    = re.findall(r'"product_id"\s*:\s*"?(\d+)"?', src)
    now    = datetime.now().strftime("%Y-%m-%d %H:%M")
    return [
        {
            "product_id":      ids[i] if i < len(ids) else f"p{i}",
            "product_name":    names[i],
            "price":           prices[i] if i < len(prices) else "0",
            "commission_rate": comms[i] if i < len(comms) else "",
            "features": "", "affiliate_link": "", "video_url": "",
            "fetched_at": now, "_detail_url": "",
        }
        for i in range(min(TOP_N, len(names)))
    ]


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 3 — Enrich: affiliate link + video URL
# ════════════════════════════════════════════════════════════════════════════

def enrich_product(driver, p: dict) -> dict:
    url  = p.get("_detail_url", "")
    name = p.get("product_name", "")[:45]
    log.info(f"  [{p.get('commission_rate','')}] {name}")

    if url and driver.current_url != url:
        driver.get(url)
        pause(2, 3.5)

    p["affiliate_link"] = _get_affiliate_link(driver)
    p["video_url"]      = _get_video_url(driver)
    return p


def _get_affiliate_link(driver) -> str:
    btn_xpaths = [
        "//button[contains(.,'Get affiliate link')]",
        "//button[contains(.,'Affiliate link')]",
        "//button[contains(.,'Get link')]",
        "//button[contains(.,'Lấy link')]",
        "//button[contains(.,'Gắn giỏ')]",
    ]
    clicked = False
    for xp in btn_xpaths:
        try:
            btn = wait_clickable(driver, By.XPATH, xp, timeout=7)
            safe_click(driver, btn)
            clicked = True
            pause(1.5, 2.5)
            break
        except TimeoutException:
            continue

    if not clicked:
        log.warning("    ⚠️  Không thấy nút affiliate link")
        return ""

    for sel in [
        "input[value*='vm.tiktok.com']",
        "input[readonly][value*='tiktok']",
        "input[readonly][value*='http']",
        "[class*='affiliate'] input",
    ]:
        try:
            inp  = WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            link = inp.get_attribute("value") or ""
            if link.startswith("http"):
                log.info(f"    ✅ {link[:55]}...")
                return link
        except TimeoutException:
            continue

    found = re.findall(r'https?://[^\s"\'<>]*tiktok\.com[^\s"\'<>]+', driver.page_source)
    aff   = [l for l in found if "vm.tiktok" in l or "affiliate" in l.lower()]
    if aff:
        return aff[0]

    log.warning("    ⚠️  Không lấy được affiliate link")
    return ""


def _get_video_url(driver) -> str:
    for sel in [
        "a[href*='tiktok.com/@'][href*='/video/']",
        "[class*='video'] a[href*='tiktok']",
    ]:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            href = el.get_attribute("href") or ""
            if "/video/" in href and "tiktok.com" in href:
                return href

    links = re.findall(
        r'https?://(?:www\.)?tiktok\.com/@[\w.]+/video/\d+',
        driver.page_source
    )
    return links[0] if links else ""


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 4 — Ghi CSV
# ════════════════════════════════════════════════════════════════════════════

def save_products(products: list[dict]):
    existing = {}
    if PRODUCTS_CSV.exists():
        with open(PRODUCTS_CSV, "r", encoding="utf-8") as f:
            existing = {r["product_id"]: r for r in csv.DictReader(f)}

    for p in products:
        pid = p.get("product_id", "")
        if not pid:
            continue
        row = {col: p.get(col, "") for col in CSV_COLUMNS}
        if not row["affiliate_link"] and pid in existing:
            row["affiliate_link"] = existing[pid].get("affiliate_link", "")
        existing[pid] = row

    with open(PRODUCTS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in existing.values():
            writer.writerow(row)

    log.info(f"💾 Đã lưu {len(existing)} sản phẩm → {PRODUCTS_CSV}")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def kill_edge():
    """Đóng Edge hoàn toàn trước khi Selenium dùng profile."""
    import subprocess
    result = subprocess.run(
        ["taskkill", "/F", "/IM", "msedge.exe", "/T"],
        capture_output=True, text=True
    )
    if "SUCCESS" in result.stdout:
        log.info("✅ Đã đóng Edge. Chờ 2 giây...")
    else:
        log.info("ℹ️  Edge không đang mở (hoặc đã đóng rồi).")
    time.sleep(2)


def run():
    log.info("=" * 58)
    log.info(f"  TikTok Affiliate Fetcher (Edge)  {datetime.now():%Y-%m-%d %H:%M}")
    log.info(f"  Top {TOP_N} | Commission cao nhất | Category: {CATEGORY}")
    log.info("=" * 58)

    kill_edge()
    driver = create_driver()
    try:
        open_and_setup(driver)

        products = scrape_top_products(driver)
        if not products:
            log.error("❌ Không lấy được sản phẩm nào.")
            return

        log.info(f"\n🔄 Đang enrich {len(products)} sản phẩm...")
        for i, p in enumerate(products, 1):
            log.info(f"\n[{i}/{len(products)}]")
            enrich_product(driver, p)
            pause(1.5, 3)

        valid   = [p for p in products if p.get("affiliate_link")]
        skipped = len(products) - len(valid)
        if skipped:
            log.warning(f"⚠️  {skipped} sản phẩm bỏ qua (không có affiliate link)")

        if valid:
            save_products(valid)
            print("\n" + "=" * 58)
            print(f"✅ XONG — {len(valid)} sản phẩm đã lưu vào products.csv")
            print("=" * 58)
            for p in valid:
                print(f"  • {p['product_name'][:42]:<44} {p['commission_rate']:>6}  {p['affiliate_link'][:35]}...")
        else:
            log.error("❌ Không có sản phẩm hợp lệ nào.")

    except RuntimeError as e:
        log.error(str(e))
    finally:
        driver.quit()


if __name__ == "__main__":
    run()