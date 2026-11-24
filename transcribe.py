"""Print every spoken word in a clip with its start and end time, so the lines of a take can be located.

Usage:  python transcribe.py take.mov

Runs fully on your own computer (nothing is uploaded). Needs:  pip install faster-whisper
The first run downloads a speech model (about 460 MB).
"""
import sys
from faster_whisper import WhisperModel

if len(sys.argv) != 2: sys.exit(__doc__)
model = WhisperModel("small.en", device="cpu", compute_type="int8")
segments, _ = model.transcribe(sys.argv[1], beam_size=5, word_timestamps=True)
for seg in segments:
    print(f"\n[{seg.start:7.2f} - {seg.end:7.2f}] {seg.text.strip()}")
    for w in seg.words:
        print(f"    {w.start:7.2f}  {w.end:7.2f}  {w.word.strip()}")
