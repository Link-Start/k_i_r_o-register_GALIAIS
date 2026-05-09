"""
hCaptcha 求解器 - YesCaptcha 第三方服务
提取 sitekey → 调用 YesCaptcha API → 注入 token
"""
import asyncio
import os
import time
import httpx
from datetime import datetime
from playwright.async_api import Page

YESCAPTCHA_API_KEY = os.environ.get("YESCAPTCHA_API_KEY", "")
YESCAPTCHA_API_URL = "https://api.yescaptcha.com"


def log(msg, level='info'):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [{level.upper():5s}] {msg}')


async def _get_sitekey(page: Page) -> str | None:
    """从页面提取 hCaptcha sitekey"""
    # 方法1: 从 data-sitekey 属性
    sitekey = await page.evaluate("""() => {
        const el = document.querySelector('[data-sitekey]');
        if (el) return el.getAttribute('data-sitekey');
        // 检查所有 iframe src 中的 sitekey
        const iframes = document.querySelectorAll('iframe');
        for (const f of iframes) {
            const src = f.src || '';
            const match = src.match(/sitekey=([a-f0-9-]+)/);
            if (match) return match[1];
        }
        return null;
    }""")
    if sitekey:
        return sitekey

    # 方法2: 从 hcaptcha iframe URL 中提取
    for frame in page.frames:
        url = frame.url
        if "hcaptcha.com" in url:
            import re
            match = re.search(r'sitekey=([a-f0-9-]+)', url)
            if match:
                return match.group(1)
            # 也可能在 host 参数里
            match = re.search(r'host=([^&]+)', url)
            if match:
                # host 不是 sitekey，继续找
                pass

    # 方法3: 从页面脚本中找
    sitekey = await page.evaluate("""() => {
        // hcaptcha render 参数
        if (window.hcaptcha && window.hcaptcha._psts) {
            for (const k of Object.keys(window.hcaptcha._psts)) {
                return k;
            }
        }
        // 搜索 script 内容
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {
            const text = s.textContent || '';
            const match = text.match(/sitekey['":\s]+['"]([a-f0-9-]{36,})['"]/);
            if (match) return match[1];
        }
        return null;
    }""")
    return sitekey


async def _create_task(sitekey: str, page_url: str, log_fn=log) -> str | None:
    """创建 YesCaptcha 任务，返回 taskId"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{YESCAPTCHA_API_URL}/createTask",
            json={
                "clientKey": YESCAPTCHA_API_KEY,
                "task": {
                    "type": "HCaptchaTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": sitekey,
                }
            }
        )
        data = resp.json()
        if data.get("errorId", 1) != 0:
            log_fn(f"YesCaptcha createTask 错误: {data.get('errorDescription', data)}", "error")
            return None
        task_id = data.get("taskId")
        log_fn(f"任务已创建: {task_id}", "info")
        return task_id


async def _get_task_result(task_id: str, log_fn=log, timeout: int = 120) -> str | None:
    """轮询获取结果，返回 token"""
    start = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() - start < timeout:
            await asyncio.sleep(5)
            resp = await client.post(
                f"{YESCAPTCHA_API_URL}/getTaskResult",
                json={
                    "clientKey": YESCAPTCHA_API_KEY,
                    "taskId": task_id,
                }
            )
            data = resp.json()
            if data.get("errorId", 1) != 0:
                log_fn(f"getTaskResult 错误: {data.get('errorDescription', data)}", "error")
                return None
            status = data.get("status")
            if status == "ready":
                token = data.get("solution", {}).get("gRecaptchaResponse")
                log_fn(f"Token 获取成功 ({len(token) if token else 0} chars)", "ok")
                return token
            log_fn(f"等待中... ({int(time.time()-start)}s)", "dbg")
    log_fn("YesCaptcha 超时", "error")
    return None


async def _inject_token(page: Page, token: str, log_fn=log) -> bool:
    """将 token 注入页面"""
    success = await page.evaluate("""(token) => {
        // 方法1: 设置 h-captcha-response textarea
        const textareas = document.querySelectorAll('textarea[name="h-captcha-response"], textarea[name="g-recaptcha-response"]');
        for (const ta of textareas) {
            ta.value = token;
            ta.innerHTML = token;
        }

        // 方法2: 设置隐藏 input
        const inputs = document.querySelectorAll('input[name="h-captcha-response"]');
        for (const inp of inputs) {
            inp.value = token;
        }

        // 方法3: 调用 hcaptcha 回调
        if (window.hcaptcha) {
            // 尝试获取 widget ID 并设置 response
            try {
                const widgetIds = Object.keys(window.hcaptcha._psts || {});
                for (const wid of widgetIds) {
                    window.hcaptcha.setResponse(token, wid);
                }
            } catch(e) {}
        }

        // 方法4: 触发全局回调
        if (window.onHCaptchaSuccess) {
            window.onHCaptchaSuccess(token);
            return true;
        }

        // 方法5: 查找并触发 data-callback
        const captchaEl = document.querySelector('[data-callback]');
        if (captchaEl) {
            const cbName = captchaEl.getAttribute('data-callback');
            if (window[cbName]) {
                window[cbName](token);
                return true;
            }
        }

        return textareas.length > 0 || inputs.length > 0;
    }""", token)

    if success:
        log_fn("Token 已注入页面", "ok")
    else:
        log_fn("注入可能未成功，尝试 frame 内注入...", "warn")
        # 尝试在 hcaptcha iframe 内注入
        for frame in page.frames:
            if "hcaptcha.com" in frame.url:
                try:
                    await frame.evaluate("""(token) => {
                        const ta = document.querySelector('textarea[name="h-captcha-response"]');
                        if (ta) ta.value = token;
                        // 触发 postMessage 回调
                        window.parent.postMessage(JSON.stringify({
                            source: 'hcaptcha',
                            label: 'challenge-closed',
                            contents: {event: 'challenge-passed', response: token, expiration: 120}
                        }), '*');
                    }""", token)
                    log_fn("通过 frame postMessage 注入", "info")
                    success = True
                except Exception as e:
                    log_fn(f"Frame 注入失败: {e}", "warn")

    return success


async def solve_hcaptcha(page: Page, log_fn=log, max_retries: int = 2) -> bool:
    """
    使用 YesCaptcha 解决 hCaptcha

    需要设置环境变量 YESCAPTCHA_API_KEY
    """
    if not YESCAPTCHA_API_KEY:
        log_fn("未设置 YESCAPTCHA_API_KEY!", "error")
        return False

    log_fn("hCaptcha 求解器启动 (YesCaptcha)", "info")

    # 提取 sitekey
    sitekey = await _get_sitekey(page)
    if not sitekey:
        log_fn("无法提取 hCaptcha sitekey", "error")
        # 等一下再试
        await asyncio.sleep(3)
        sitekey = await _get_sitekey(page)
        if not sitekey:
            return False

    page_url = page.url
    log_fn(f"sitekey: {sitekey}", "info")
    log_fn(f"pageURL: {page_url[:80]}...", "info")

    for attempt in range(1, max_retries + 1):
        log_fn(f"--- 尝试 {attempt}/{max_retries} ---", "info")

        # 创建任务
        task_id = await _create_task(sitekey, page_url, log_fn)
        if not task_id:
            await asyncio.sleep(3)
            continue

        # 等待结果
        token = await _get_task_result(task_id, log_fn)
        if not token:
            continue

        # 注入 token
        injected = await _inject_token(page, token, log_fn)
        if injected:
            await asyncio.sleep(2)
            # 检查 challenge 是否消失
            challenge_gone = True
            for frame in page.frames:
                if "hcaptcha.com" in frame.url and "frame=challenge" in frame.url:
                    for f_el in await page.query_selector_all("iframe"):
                        src = await f_el.get_attribute("src") or ""
                        if "frame=challenge" in src and await f_el.is_visible():
                            challenge_gone = False
                            break
            if challenge_gone:
                log_fn("hCaptcha 验证通过!", "ok")
                return True
            else:
                log_fn("Token 注入后 challenge 仍在，重试...", "warn")

    log_fn("YesCaptcha 求解失败", "error")
    return False
