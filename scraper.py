def sync_to_google_sheet(new_videos):
    """將新抓取的影片同步寫入 Google 試算表（加入完整防護避免中斷）"""
    if not new_videos:
        print("本次無新影片需要同步至 Google 試算表。")
        return

    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not creds_json or not sheet_id:
        print("⚠️ 未設定 Google 試算表相關 Secrets，跳過試算表同步。")
        return

    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(sheet_id).sheet1

        # 若工作表完全空白，自動寫入表頭
        if not sheet.get_all_values():
            sheet.append_row(["標題", "女優", "標籤", "影片連結", "封面連結", "抓取時間"])

        for v in new_videos:
            sheet.append_row([
                v["title"],
                v["actress"] or "未知",
                v["tags"] or "",
                v["video_url"],
                v["cover_url"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])
        print("✅ 成功同步新影片至 Google 試算表！")
    except Exception as e:
        print(f"❌ 同步 Google 試算表失敗 (略過以繼續執行): {e}")
        import traceback
        traceback.print_exc()
