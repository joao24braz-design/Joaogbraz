import json,sys
from pathlib import Path
from app import transcribe
print(json.dumps(transcribe(Path(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else ''),ensure_ascii=False))
