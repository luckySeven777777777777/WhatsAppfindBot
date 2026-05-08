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
                # 20秒超时，防止网络波动
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
        # 增加等待时间
        await page.goto(url, wait_until="networkidle", timeout=80000)
        invalid_sel = 'text="Phone number shared via url is invalid"'
        chat_sel = 'footer'
        for _ in range(20):
            if await page.query_selector(invalid_sel): return "未注册"
            if await page.query_selector(chat_sel): return "已注册✅"
            await asyncio.sleep(1)
        return "超时"
    except: return "异常"
    finally: await page.close()

async def main():
    async with async_playwright() as p:
        print("🚀 正在云端初始化检测引擎...")
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        page = await context.new_page()
        
        # 启动测试
        send_to_tg("🔔 系统提示：WhatsApp 检测程序已在 Railway 启动，正在加载页面...")

        print("🔗 正在访问 WhatsApp Web...")
        try:
            await page.goto("https://web.whatsapp.com", timeout=120000)
        except Exception as e:
            print(f"页面加载超时: {e}")

        # --- 增强版二维码检测逻辑 ---
        print("⌛ 正在循环探测二维码...")
        qr_sent = False
        # 尝试检测 30 次，每次间隔 3 秒，总计 90 秒
        for i in range(30):
            qr_canvas = await page.query_selector("canvas")
            if qr_canvas:
                print(f"📢 发现二维码 (尝试次数: {i+1})，正在截图...")
                await asyncio.sleep(3) # 额外多等几秒确保二维码画完
                qr_path = "qr_login.png"
                await page.screenshot(path=qr_path)
                send_to_tg("⚠️ 发现登录二维码，请尽快扫码！", qr_path)
                qr_sent = True
                break
            
            # 检测是否已经自动登录了（看到对话框footer）
            if await page.query_selector("#pane-side") or await page.query_selector("footer"):
                print("✅ 检测到已登录状态，跳过扫码。")
                qr_sent = True
                break
                
            await asyncio.sleep(3)

        if not qr_sent:
            print("❌ 90秒内未发现二维码，发送错误排查截图...")
            err_path = "error_diagnostic.png"
            await page.screenshot(path=err_path)
            send_to_tg("❌ 未能捕获到二维码。请检查此诊断截图，确认网页加载状态：", err_path)
            # 如果没码也没登录，后续无法操作，直接返回
            return

        # 等待登录成功后的界面加载
        if qr_canvas:
            print("⌛ 等待扫码结果...")
            for _ in range(90): # 再给 3 分钟扫码
                if not await page.query_selector("canvas"):
                    print("✅ 登录成功！")
                    send_to_tg("✅ 登录成功，正在扫描本地文件...")
                    break
                await asyncio.sleep(2)

        # 处理文件
        files = [f for f in os.listdir(CONTACTS_DIR) if f.endswith(".xlsx")]
        if not files:
            print("❌ contacts 文件夹里没文件！")
            send_to_tg("❌ 错误：在 contacts 文件夹里没找到任何 .xlsx 文件！")
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
                results.append({"手机号": phone, "状态": status, "检测时间": current_time})
                # 随机延迟保护账号
                await asyncio.sleep(random.uniform(5, 10))

            output_file = f"checked_{file_name}"
            output_path = os.path.join(OUTPUT_DIR, output_file)
            pd.DataFrame(results).to_excel(output_path, index=False)
            send_to_tg(f"📊 任务完成: {file_name}\n数量: {len(results)}", output_path)

        await context.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"系统运行崩溃: {e}")
