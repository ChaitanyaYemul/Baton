"""Send synthetic text only; print provider status without credentials or source output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engine import extract

claims, mode = extract([{'id': 'connection-check', 'text':
    'Decision: keep payments in test mode until approval. Owner: Kabir.'}])
print('Provider result:', mode)
print('Validated claims:', len(claims))
sys.exit(0 if not mode.startswith('offline') else 1)
