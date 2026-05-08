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
    """发送通知到 TG (增强版：带错误日志和长超时)"""
    print(f"【系统日志】: 尝试发送消息 - {text}")
    try:
        if file_path and os.path.exists(file_path):
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                # 增加到 20秒超时，防止云端网络波动
                resp = requests.post(url, data={'chat_id': CHAT_ID, 'caption': text}, files={'document': f}, timeout=20)
                print(f"【系统日志】: 文件发送响应 - {resp.status_code}")
        else:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            resp = requests.post(url, data={'chat_id': CHAT_ID, 'text': text}, timeout=10)
            print(f"【系统日志】: 文字发送响应 - {resp.status_code}")
    except Exception as e:
        print(f"【错误】TG 推送失败: {e}")

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
        
        # 在云端必须 headless=True
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        page = await context.new_page()
        
        # 启动测试：发一条文字消息，确认机器人通了
        send_to_tg("🔔 系统提示：WhatsApp 检测程序已在 Railway 启动...")

        print("🔗 正在访问 WhatsApp Web...")
        await page.goto("https://web.whatsapp.com")
        
        # 等待二维码出现
        print("⌛ 等待页面加载...")
        await asyncio.sleep(15) 
        
        qr_canvas = await page.query_selector("canvas")
        if qr_canvas:
            print("📢 捕获到二维码，准备截图并发送...")
            qr_path = "qr_login.png"
            await page.screenshot(path=qr_path)
            
            # 尝试发送二维码
            send_to_tg("⚠️ 请扫码登录 WhatsApp", qr_path)
            
            # 给 3 分钟扫码时间
            print("⌛ 正在等待扫码 (3分钟窗口)...")
            for i in range(90):
                if not await page.query_selector("canvas"):
                    print("✅ 扫码成功，进入系统！")
                    send_to_tg("✅ 登录成功，开始检测任务！")
                    break
                await asyncio.sleep(2)
        else:
            print("💡 未发现二维码，可能已处于登录状态。")

        # 处理文件
        files = [f for f in os.listdir(CONTACTS_DIR) if f.endswith(".xlsx")]
        if not files:
            print("❌ contacts 文件夹里没文件！")
            send_to_tg("❌ 错误：contacts 文件夹里找不到 .xlsx 文件！")
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
            send_to_tg(f"📊 任务完成: {file_name}", output_path)

        await context.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"程序崩溃: {e}")
