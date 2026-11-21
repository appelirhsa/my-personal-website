"""Generate the ADMIN_PASSWORD_HASH line for server/.env.  Run:  python server/hash_password.py"""
import getpass, hashlib, os

pw = getpass.getpass("New admin password (12+ characters): ")
if len(pw) < 12:
    raise SystemExit("Use at least 12 characters.")
if pw != getpass.getpass("Repeat: "):
    raise SystemExit("Passwords do not match.")
salt = os.urandom(16)
digest = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
print(f"\nADMIN_PASSWORD_HASH={salt.hex()}:{digest.hex()}")
