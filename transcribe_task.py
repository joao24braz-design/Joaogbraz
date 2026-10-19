import json,sys
from pathlib import Path
from app import transcribe
print(json.dumps(transcribe(Path(sys.argv[1])),ensure_ascii=False))
