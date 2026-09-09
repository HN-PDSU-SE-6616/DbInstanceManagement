"""工具层"""
import secrets
import socket
import string

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_SPECIAL_CHARS = "!@#$%^&*-_=+?"
_PASSWORD_CHARSET = string.ascii_letters + string.digits + _SPECIAL_CHARS


def get_cipher() -> Fernet:
    """构造 Fernet 加密器

    :Return: Fernet 实例
    """
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("缺少 ENCRYPTION_KEY，请检查 .env 文件")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("ENCRYPTION_KEY 不是有效的 Fernet 密钥") from exc


def encrypt_password(plain: str) -> str:
    """加密明文密码

    :param plain: 明文密码
    :Return: Fernet 密文字符串
    """
    if not plain:
        return ""
    return get_cipher().encrypt(str(plain).encode()).decode()


def decrypt_password(token: str) -> str:
    """解密密码密文

    :param token: Fernet 密文字符串
    :Return: 明文密码
    """
    if not token:
        return ""
    try:
        return get_cipher().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("密码解密失败：ENCRYPTION_KEY 可能已更换") from exc


def generate_strong_password(length: int = 16) -> str:
    """生成包含大小写字母、数字与特殊字符的随机强密码"""
    length = max(length, 8)
    while True:
        candidate = "".join(secrets.choice(_PASSWORD_CHARSET) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(c in _SPECIAL_CHARS for c in candidate)
        ):
            return candidate


def check_port_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    """检测 TCP 端口是否可达。

    :param host: IP 或域名。
    :param port: 端口号（1-65535），越界直接视为不可达。
    :param timeout: 连接超时秒数。
    :Return: 可达返回 True，不可达/非法输入返回 False。
    """
    if not (0 < port < 65536):
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False
