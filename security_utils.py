# ==========================================
# 文件: security_utils.py
# 说明：机器码与API加密工具
# 作者：lk (569261093@qq.com)
# 版本：1.0.0
# ==========================================
import base64
import hashlib
import platform
import uuid


# 生成Windows机器唯一标识（优先使用MachineGuid）
def _get_windows_machine_guid():
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except Exception:
        return ""


# 获取本机机器码
def get_machine_code():
    parts = []
    machine_guid = _get_windows_machine_guid()
    if machine_guid:
        parts.append(machine_guid)
    parts.extend(
        [
            platform.system(),
            platform.release(),
            platform.node(),
            str(uuid.getnode()),
        ]
    )
    raw = "|".join([item for item in parts if item])
    if not raw:
        raw = "AI-TUTOR-UNKNOWN"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return digest[:32]


# 根据机器码派生加密密钥
def _derive_key(machine_code):
    payload = f"AI-TUTOR|{machine_code}".encode("utf-8")
    return hashlib.sha256(payload).digest()


# 加密API Key
def encrypt_api_key(api_key, machine_code, base_url="", model="", expire_at=""):
    if not api_key or not machine_code:
        return ""
    base_url = (base_url or "").strip()
    model = (model or "").strip()
    expire_at = (expire_at or "").strip()
    if base_url or model or expire_at:
        payload = f"AI-TUTOR|v3|{api_key}|{base_url}|{model}|{expire_at}"
    else:
        payload = f"AI-TUTOR|{api_key}"
    plain_text = payload.encode("utf-8")
    key = _derive_key(machine_code)
    cipher = bytes(
        byte ^ key[index % len(key)] for index, byte in enumerate(plain_text)
    )
    return base64.urlsafe_b64encode(cipher).decode("utf-8")


# 解密API Key
def decrypt_api_key(token, machine_code):
    if not token or not machine_code:
        return {}
    try:
        cipher = base64.urlsafe_b64decode(token.encode("utf-8"))
        key = _derive_key(machine_code)
        plain = bytes(
            byte ^ key[index % len(key)] for index, byte in enumerate(cipher)
        )
        text = plain.decode("utf-8")
        if not text.startswith("AI-TUTOR|"):
            return {}
        parts = text.split("|")
        if len(parts) >= 3 and parts[1] == "v3":
            return {
                "api_key": parts[2].strip(),
                "base_url": parts[3].strip() if len(parts) > 3 else "",
                "model": parts[4].strip() if len(parts) > 4 else "",
                "expire_at": parts[5].strip() if len(parts) > 5 else "",
            }
        if len(parts) >= 3 and parts[1] == "v2":
            return {
                "api_key": parts[2].strip(),
                "base_url": parts[3].strip() if len(parts) > 3 else "",
                "model": parts[4].strip() if len(parts) > 4 else "",
                "expire_at": "",
            }
        api_key = text.split("AI-TUTOR|", 1)[1].strip()
        return {"api_key": api_key, "base_url": "", "model": "", "expire_at": ""}
    except Exception:
        return {}
