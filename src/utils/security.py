import os
from cryptography.fernet import Fernet

# You will generate this key once and put it in Streamlit Secrets
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")

def encrypt_text(text: str) -> str:
    if not ENCRYPTION_KEY: return text
    f = Fernet(ENCRYPTION_KEY.encode())
    return f.encrypt(text.encode()).decode()

def decrypt_text(text: str) -> str:
    if not ENCRYPTION_KEY: return text
    try:
        f = Fernet(ENCRYPTION_KEY.encode())
        return f.decrypt(text.encode()).decode()
    except:
        return "Decryption Error: Check keys."