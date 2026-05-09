"""TempForward 临时邮箱服务 (自建)"""
import json
import re
import time

from .base import MailProvider


def _safe_json(resp):
    """安全解析响应 JSON，处理多 JSON 拼接或前缀垃圾"""
    raw = resp.text.strip()
    try:
        return resp.json()
    except Exception:
        pass
    # 尝试找到第一个 '{' 开始解析
    idx = raw.find('{')
    if idx >= 0:
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(raw[idx:])
            return obj
        except Exception:
            pass
    raise RuntimeError(f"TempForward 响应非 JSON: {raw[:200]}")


class TempForwardProvider(MailProvider):

    name = "tempforward"
    display_name = "TempForward"

    def __init__(self, base_url: str = "", **_kwargs):
        import requests as _req
        base_url = base_url.rstrip("/")
        # 兼容用户填入 http://host:port/api/v1 的情况
        if base_url.endswith("/api/v1"):
            base_url = base_url[:-len("/api/v1")]
        elif base_url.endswith("/api"):
            base_url = base_url[:-len("/api")]
        self.base_url = base_url
        self.session = _req.Session()
        self.session.verify = False
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self.token = None
        self.address = None

    def create_mailbox(self) -> str:
        resp = self.session.post(
            f"{self.base_url}/api/v1/mailboxes/create",
            json={"expiry_hours": 3},
            timeout=15,
        )
        data = _safe_json(resp)
        if not data.get("ok"):
            err = data.get("error", {})
            raise RuntimeError(f"TempForward 创建邮箱失败: {err.get('message', data)}")
        mailbox = data["data"]["mailbox"]
        self.token = mailbox["token"]
        self.address = mailbox["address"]
        return self.address

    def wait_otp(self, timeout: int = 120, poll_interval: int = 3) -> str:
        if not self.token:
            return ""
        # 优先使用服务端长轮询 wait-code 接口
        try:
            resp = self.session.post(
                f"{self.base_url}/api/v1/mailboxes/wait-code",
                json={
                    "token": self.token,
                    "timeout_seconds": timeout,
                    "poll_interval_ms": poll_interval * 1000,
                    "require_code": True,
                },
                timeout=timeout + 10,
            )
            data = _safe_json(resp)
            if data.get("ok"):
                code = data["data"].get("primary_code", "")
                if code and re.match(r'^\d{4,8}$', code):
                    return code
                codes = data["data"].get("codes", [])
                for c in codes:
                    if re.match(r'^\d{6}$', c):
                        return c
        except Exception:
            pass
        # 回退: 客户端轮询 inbox
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                resp = self.session.get(
                    f"{self.base_url}/api/v1/mailboxes/inbox",
                    params={"token": self.token},
                    timeout=10,
                )
                data = _safe_json(resp)
                if data.get("ok"):
                    emails = data["data"].get("emails", [])
                    if emails:
                        email_id = emails[0]["id"]
                        detail_resp = self.session.get(
                            f"{self.base_url}/api/v1/mailboxes/emails/{email_id}",
                            params={"token": self.token},
                            timeout=10,
                        )
                        detail_data = _safe_json(detail_resp)
                        if detail_data.get("ok"):
                            email = detail_data["data"]
                            body = email.get("text_body", "") or email.get("html_body", "")
                            match = re.search(r'\b(\d{6})\b', body)
                            if match:
                                return match.group(1)
            except Exception:
                pass
            time.sleep(poll_interval)
        return ""

    def list_domains(self) -> list[dict]:
        # TempForward 由服务端自动分配域名
        return [{"id": "auto", "domain": "(自动分配)"}]
