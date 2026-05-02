"""
Credential Vault — inspired by Vessel's Agent Credential Vault.
Encrypted credential storage with domain scoping, TOTP, and blind fill.
Credentials are NEVER sent to AI providers — they flow directly to page forms.
"""
import keyring, json, os, pyotp, base64, hashlib
from cryptography.fernet import Fernet
from pathlib import Path
from typing import Optional, List
from datetime import datetime

VAULT_DIR = Path("~/.agent-browser/vault").expanduser()
VAULT_DIR.mkdir(parents=True, exist_ok=True)
VAULT_MASTER_KEY_FILE = VAULT_DIR / ".master.key"
VAULT_CREDENTIALS_FILE = VAULT_DIR / "credentials.enc"
VAULT_AUDIT_FILE = VAULT_DIR / "audit.log"
AUDIT_MODE = 0o600

# Internal token for vault endpoint authentication (prevents credential exfiltration)
_VAULT_TOKEN = os.getenv("VAULT_API_TOKEN", "agent-browser-internal-dev-token")

class CredentialVault:
    def __init__(self):
        self._ensure_master_key()
        self._fernet = Fernet(self._load_master_key())
    
    def _ensure_master_key(self):
        """Get or create master key via OS keychain, fallback to file."""
        import keyring.errors
        try:
            key = keyring.get_password("agent-browser-vault", "master-key")
            if key:
                self._master_key = key.encode()
                return
        except keyring.errors.NoKeyringError:
            pass

        # Fallback: file-based key storage
        if VAULT_MASTER_KEY_FILE.exists():
            self._master_key = VAULT_MASTER_KEY_FILE.read_bytes()
            return

        # Generate new key and store to file
        new_key = Fernet.generate_key()
        VAULT_MASTER_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        VAULT_MASTER_KEY_FILE.write_bytes(new_key)
        VAULT_MASTER_KEY_FILE.chmod(0o600)
        self._master_key = new_key
    
    def _load_master_key(self) -> bytes:
        return self._master_key
    
    # ── Credential CRUD ───────────────────────────────────────────────
    
    def add_credential(
        self,
        domain: str,
        username: str,
        password: str,
        totp_secret: Optional[str] = None,
        label: Optional[str] = None,
    ) -> dict:
        """Store a credential for a domain."""
        credential_id = hashlib.sha256(f"{domain}:{username}".encode()).hexdigest()[:16]
        entry = {
            "id": credential_id,
            "domain": domain,
            "username": username,
            "password": password,  # encrypted at rest via vault file
            "totp_secret": totp_secret,
            "label": label or username,
            "created_at": datetime.utcnow().isoformat(),
            "use_count": 0,
        }
        self._save_credential(entry)
        self._audit("add", credential_id, domain)
        return {"id": credential_id, "domain": domain, "label": entry["label"]}
    
    def get_credential(self, domain: str) -> Optional[dict]:
        """Get credential (without password) for a domain. Returns labels/usernames only."""
        creds = self._load_all()
        for c in creds:
            if c["domain"] == domain:
                return {"id": c["id"], "domain": c["domain"], "username": c["username"], "label": c["label"]}
        return None
    
    def fill_credential(self, domain: str) -> dict:
        """
        Blind fill — returns actual credential for page form injection.
        NEVER returns password to AI — only to the form filler.
        """
        creds = self._load_all()
        for c in creds:
            if c["domain"] == domain:
                c["use_count"] += 1
                self._save_credential(c)
                self._audit("fill", c["id"], domain)
                
                # Generate TOTP if secret exists
                totp_code = None
                if c.get("totp_secret"):
                    totp_code = pyotp.TOTP(c["totp_secret"]).now()
                
                return {
                    "username": c["username"],
                    "password": c["password"],
                    "totp_code": totp_code,
                }
        return {"error": f"No credential found for {domain}"}
    
    def list_domains(self) -> List[str]:
        """List all domains with stored credentials."""
        creds = self._load_all()
        return [c["domain"] for c in creds]
    
    def delete_credential(self, credential_id: str) -> dict:
        """Delete a credential."""
        creds = self._load_all()
        creds = [c for c in creds if c["id"] != credential_id]
        self._write_all(creds)
        self._audit("delete", credential_id, "")
        return {"deleted": True}
    
    # ── Internal ─────────────────────────────────────────────────────
    
    def _load_all(self) -> list:
        if not VAULT_CREDENTIALS_FILE.exists():
            return []
        try:
            encrypted = VAULT_CREDENTIALS_FILE.read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted)
        except Exception:
            return []
    
    def _write_all(self, creds: list):
        encrypted = self._fernet.encrypt(json.dumps(creds).encode())
        VAULT_CREDENTIALS_FILE.write_bytes(encrypted)
        os.chmod(VAULT_CREDENTIALS_FILE, 0o600)
    
    def _save_credential(self, entry: dict):
        creds = self._load_all()
        # Replace or append
        for i, c in enumerate(creds):
            if c["id"] == entry["id"]:
                creds[i] = entry
                break
        else:
            creds.append(entry)
        self._write_all(creds)
    
    def _audit(self, action: str, credential_id: str, domain: str):
        """Append-only audit log."""
        ts = datetime.utcnow().isoformat()
        line = f"{ts} {action.upper()} {credential_id} {domain}\n"
        with open(VAULT_AUDIT_FILE, "a") as f:
            f.write(line)
        os.chmod(VAULT_AUDIT_FILE, 0o600)
