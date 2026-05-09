"""邮件服务提供者抽象基类"""
from abc import ABC, abstractmethod


class MailProvider(ABC):
    """邮件服务提供者基类"""

    name: str = "base"
    display_name: str = "Base Provider"

    @abstractmethod
    def create_mailbox(self) -> str:
        """创建临时邮箱，返回邮箱地址"""
        ...

    @abstractmethod
    def wait_otp(self, timeout: int = 120, poll_interval: int = 3) -> str:
        """轮询等待 OTP 验证码，返回 6 位数字或空字符串"""
        ...

    @abstractmethod
    def list_domains(self) -> list[dict]:
        """
        获取可用域名列表
        返回: [{"id": "...", "domain": "..."}, ...]
        """
        ...
