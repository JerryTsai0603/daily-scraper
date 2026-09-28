import os
import asyncio
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

# --- 讀取雲端環境變數 ---
DB_FILE = "videos.db"
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "edgedge0603@gmail.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            cover_url TEXT,
            tags TEXT,
            video_url TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_video(title, cover_url, tags, video_url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO videos (title, cover_url, tags, video_url)
            VALUES (?, ?, ?, ?)
        """, (title, cover_url, tags, video_url))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def send_email_report(new_videos):
    if not new_videos:
        print("本次無新增影片，不寄送通知信。")
        return

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("未設定寄件者帳號或密碼，略過郵件發送。")
        return

    subject = f"【每日影片爬蟲報告】今日新增 {len(new_videos)} 部符合條件的影片"
    
    items_html = ""
    for v in new_videos:
        items_html += f"""
        <div style="border:1px solid #e2e8f0; border-radius:8px; padding:12px; margin-bottom:15px; background-color:#f8fafc;">
            <div style="display:flex; gap:12px; align-items:center;">
                <img src="{v['cover_url']}" alt="封面" style="width:160px; height:100px; object-fit:cover; border-radius:6px;" referrerpolicy="no-referrer">
                <div>
                    <h3 style="margin:0 0 6px 0; font-size:15px; color:#0f172a;">{v['title']}</h3>
                    <p style="margin:0 0 8px 0; font-size:12px; color:#64748b;">標籤：{v['tags'] or '無'}</p>
                    <a href="{v['video_url']}" target="_blank" style="display:inline-block; padding:6px 12px; background-color:#0284c7; color:#fff; text-decoration:none; border-radius:4px; font-size:12px;">前往觀看</a>
                </div>
            </div>
        </div>
        """

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.5;">
            <h2>每日爬蟲更新通知</h2>
            <p>本次排程共篩選並新入庫 <strong>{len(new_videos)}</strong> 部影片：</p>
            {items_html}
        </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        print(f"正在寄送通知信至 {RECIPIENT_EMAIL}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print("✅ 郵件寄送成功！")
    except Exception as e:
        print(f"❌ 郵件寄送失敗: {e}")

async def run_scraper():
    init_db()
    keywords = ["絲襪", "黑絲", "白絲", "肉絲", "網襪", "腳交", "足交", "玩腳", "舔腳", "腳", "足"]
    seen_urls = set()
    newly_added_videos = []

    async with Stealth().use_async(async_playwright()) as p:
        try:
            # 雲端環境使用無頭模式與內建 chromium
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            for page_num in range(1, 3):
                target_url = "https://jable.tv/categories/chinese-subtitle/" if page_num == 1 else f"https://jable.tv/categories/chinese-subtitle/{page_num}/"
                print(f"\n正在掃描第 {page_num}/2 頁: {target_url}")

                try:
                    await page.goto(target_url, timeout=60000)
                    await page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"無法載入第 {page_num} 頁: {e}")
                    continue

                for _ in range(2):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    await page.wait_for_timeout(1500)

                soup = BeautifulSoup(await page.content(), 'html.parser')
                video_boxes = soup.select('.video-img-box')

                page_links = []
                for box in video_boxes:
                    link_elem = box.find('a', href=True)
                    if link_elem and '/videos/' in link_elem['href']:
                        full_url = link_elem['href'] if link_elem['href'].startswith('http') else f"https://jable.tv{link_elem['href']}"
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            page_links.append(full_url)

                for idx, video_url in enumerate(page_links, 1):
                    try:
                        await page.goto(video_url, timeout=30000)
                        await page.wait_for_timeout(1500)

                        detail_soup = BeautifulSoup(await page.content(), 'html.parser')
                        title_elem = detail_soup.select_one('h4') or detail_soup.select_one('h1') or detail_soup.find('title')
                        video_title = title_elem.text.strip().replace(" - Jable.tv", "").strip() if title_elem else "未知標題"

                        img_meta = detail_soup.select_one('meta[property="og:image"]')
                        cover_image_url = img_meta.get('content') if img_meta else ""

                        h5_tags = detail_soup.find_all('h5')
                        h5_text = " ".join([h.text.strip() for h in h5_tags])

                        if any(kw in h5_text for kw in keywords) or any(kw in video_title for kw in keywords):
                            if save_video(video_title, cover_image_url, h5_text, video_url):
                                newly_added_videos.append({
                                    "title": video_title,
                                    "cover_url": cover_image_url,
                                    "tags": h5_text,
                                    "video_url": video_url
                                })
                                print(f"  🎯 [新收錄] {video_title}")
                            else:
                                print(f"  ℹ️ [已存在] {video_title}")

                    except Exception as err:
                        continue

            print(f"\n✅ 爬取結束！本次新收錄 {len(newly_added_videos)} 部影片")
            send_email_report(newly_added_videos)

        finally:
            if 'browser' in locals() and browser:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())