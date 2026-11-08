"""Load backend-only local configuration without overriding host-provided secrets."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
