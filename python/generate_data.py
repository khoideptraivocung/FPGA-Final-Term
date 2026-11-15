"""Generate deterministic 1024-sample signed 12-bit ROM data."""
from pathlib import Path
import numpy as np

N = 1024
rng = np.random.default_rng(22)
n = np.arange(N)
x = (1050*np.sin(2*np.pi*0.025*n)
     + 260*np.sin(2*np.pi*0.22*n)
     + rng.normal(0, 105, N))
x = np.clip(np.rint(x), -2048, 2047).astype(np.int16)

def to_hex12(v):
    return f"{int(v) & 0xFFF:03X}"

root = Path(__file__).resolve().parents[1]
rom = root / "rom" / "test_vectors.mem"
rom.parent.mkdir(exist_ok=True)
rom.write_text("\\n".join(to_hex12(v) for v in x) + "\\n", encoding="ascii")
print(f"Generated {len(x)} samples -> {rom}")
