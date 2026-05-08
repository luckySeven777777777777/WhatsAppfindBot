import asyncio
import os
import pandas as pd
from playwright.async_api import async_playwright
import random
from datetime import datetime
import requests

# ================= 配置区域 =================
TG_TOKEN = "8238089253:AAEoo_Zxg4sSGggqZ3t3smu_-zraG3S6lbI" 
CHAT_ID = "6062973135" 

SESSION_DIR = "./whatsapp_sessions"
CONTACTS_DIR = "./contacts"
OUTPUT_DIR = "./results"

os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(CONTACTS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= 功能函数 =================

def send_to_tg(text, file_path=None):
    """发送通知到 TG (带 5s 硬超时，防止卡死)"""
    print(f"【系统日志】: {text}")
    try:
        if file_path:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                requests.post(url, data={'chat_id': CHAT_ID, 'caption': text}, files={'document': f}, timeout=5)
        else:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            requests.post(url, data={'chat_id': CHAT_ID, 'text': text}, timeout=5)
    except:
        print("【提示】TG 推送失败，可能是网络问题。")

async def check_number(context, phone):
    """号码检测逻辑"""
    page = await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    url = f"https://web.whatsapp.com/send?phone={phone}"
    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
        invalid_sel = 'text="Phone number shared via url is invalid"'
        chat_sel = 'footer'
        for _ in range(15):
            if await page.query_selector(invalid_sel): return "未注册"
            if await page.query_selector(chat_sel): return "已注册✅"
            await asyncio.sleep(1)
        return "超时"
    except: return "异常"
    finally: await page.close()

async def main():
    async with async_playwright() as p:
        print("🚀 正在云端初始化检测引擎...")
        
        # Railway 环境会自动设置 RAILWAY_ENVIRONMENT 变量
        is_cloud = os.getenv("RAILWAY_ENVIRONMENT") is not None
        
        # 在云端必须 headless=True
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True, # 云端运行必须隐藏窗口
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        page = await context.new_page()
        print("🔗 正在访问 WhatsApp Web...")
        await page.goto("https://web.whatsapp.com")
        
        # 登录逻辑
        await asyncio.sleep(10)
        qr_canvas = await page.query_selector("canvas")
        if qr_canvas:
            print("📢 需要扫码，正在发送二维码到 Telegram...")
            await page.screenshot(path="qr_login.png")
            send_to_tg("⚠️ 请扫码登录 WhatsApp", "qr_login.png")
            
            # 给 2 分钟扫码时间
            for i in range(60):
                if not await page.query_selector("canvas"):
                    print("✅ 登录成功！")
                    break
                await asyncio.sleep(2)

        # 处理文件
        files = [f for f in os.listdir(CONTACTS_DIR) if f.endswith(".xlsx")]
        if not files:
            print("❌ contacts 文件夹里没文件！")
            return

        for file_name in files:
            print(f"📂 开始处理: {file_name}")
            df = pd.read_excel(os.path.join(CONTACTS_DIR, file_name))
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            results = []

            for index, row in df.iterrows():
                phone = str(row.get('phone', '')).strip().replace("+", "").split(".")[0]
                if not phone or phone == 'nan': continue
                
                status = await check_number(context, phone)
                print(f"[{index+1}/{len(df)}] {phone} -> {status}")
                results.append({"手机号": phone, "状态": status, "时间": current_time})
                await asyncio.sleep(random.uniform(5, 10))

            output_file = f"checked_{file_name}"
            output_path = os.path.join(OUTPUT_DIR, output_file)
            pd.DataFrame(results).to_excel(output_path, index=False)
            send_to_tg(f"✅ 任务完成: {file_name}", output_path)

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())