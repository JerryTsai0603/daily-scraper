import os
import asyncio
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

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

def get_all_videos():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, cover_url, tags, video_url, created_at FROM videos ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def generate_index_html():
    """讀取資料庫並自動產生靜態 index.html"""
    videos = get_all_videos()
    
    cards_html = ""
    for v in videos:
        cards_html += f"""
        <div class="card">
            <img src="{v[2] or 'https://via.placeholder.com/300x180?text=No+Cover'}" alt="封面" loading="lazy" referrerpolicy="no-referrer">
            <div class="card-body">
                <div class="title" title="{v[1]}">{v[1]}</div>
                <div class="tags" title="{v[3]}">{v[3] or '無標籤'}</div>
                <div class="footer">
                    <span class="date">{v[5][:10] if v[5] else ''}</span>
                    <a href="{v[4]}" target="_blank" class="btn">前往觀看</a>
                </div>
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jable 影片收藏庫</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #0b0f19; color: #f8fafc; padding: 30px 16px; }}
        .header {{ text-align: center; margin-bottom: 35px; }}
        .header h1 {{ font-size: 1.8rem; color: #38bdf8; margin-bottom: 8px; }}
        .header p {{ color: #94a3b8; font-size: 0.9rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1400px; margin: 0 auto; }}
        .card {{ background: #1e293b; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); display: flex; flex-direction: column; transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-4px); }}
        .card img {{ width: 100%; height: 180px; object-fit: cover; background: #334155; }}
        .card-body {{ padding: 14px; flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between; }}
        .title {{ font-size: 0.95rem; font-weight: 600; line-height: 1.4; color: #f1f5f9; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 8px; }}
        .tags {{ font-size: 0.75rem; color: #94a3b8; background: #0f172a; padding: 4px 8px; border-radius: 4px; margin-bottom: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .footer {{ display: flex; justify-content: space-between; align-items: center; margin-top: auto; }}
        .date {{ font-size: 0.75rem; color: #64748b; }}
        .btn {{ background: #0284c7; color: #fff; text-decoration: none; padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; }}
        .btn:hover {{ background: #0369a1; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Jable 影片自動典藏庫</h1>
        <p>目前資料庫共收藏 {len(videos)} 部影片</p>
    </div>
    <div class="grid">
        {cards_html}
    </div>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ 已成功產出最新 index.html")

def send_email_report(new_videos):
    if not new_videos or not SENDER_EMAIL or not SENDER_PASSWORD:
        return

    subject = f"【每日影片爬蟲報告】今日新增 {len(new_videos)} 部符合條件的影片"
    items_html = "".join([
        f"""<div style="border:1px solid #e2e8f0; border-radius:8px; padding:12px; margin-bottom:12px;">
            <img src="{v['cover_url']}" style="width:160px; height:100px; object-fit:cover; border-radius:4px;" referrerpolicy="no-referrer">
            <h4 style="margin:6px 0;">{v['title']}</h4>
            <a href="{v['video_url']}" target="_blank">前往觀看</a>
        </div>""" for v in new_videos
    ])
    html_content = f"<h2>今日更新通知</h2><p>本次新增 <strong>{len(new_videos)}</strong> 部：</p>{items_html}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
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
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            for page_num in range(1, 3):
                target_url = "https://jable.tv/categories/chinese-subtitle/" if page_num == 1 else f"https://jable.tv/categories/chinese-subtitle/{page_num}/"
                print(f"正在掃描第 {page_num}/2 頁: {target_url}")

                try:
                    await page.goto(target_url, timeout=60000)
                    await page.wait_for_timeout(3000)
                except Exception as e:
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
                    except Exception:
                        continue

            print(f"✅ 爬取結束！新收錄 {len(newly_added_videos)} 部影片")
            
            # 生成 index.html
            generate_index_html()
            
            # 寄出郵件
            send_email_report(newly_added_videos)

        finally:
            if 'browser' in locals() and browser:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())