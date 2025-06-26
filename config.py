import sys
import os

secret_key = os.urandom(24)

ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
if not ADMIN_PASSWORD_HASH:
    print("\n❌ FOUT: ADMIN_PASSWORD_HASH is niet ingesteld als omgevingsvariabele.")
    print("Gebruik bijvoorbeeld:")
    print("  python -c \"import bcrypt; print(bcrypt.hashpw(b'geheim', bcrypt.gensalt()).decode())\"")
    print("en stel deze in via:")
    print("  export ADMIN_PASSWORD_HASH='...' (Linux/macOS)")
    print("  set ADMIN_PASSWORD_HASH=...       (Windows)")
    sys.exit(1)