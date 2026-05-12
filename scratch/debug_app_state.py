import sys
from pathlib import Path
import json

# Add scripts to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

import jmty_gui

try:
    state = jmty_gui.app_state(jmty_gui.DEFAULT_OUTPUT_ROOT, jmty_gui.DEFAULT_TEMPLATES_DIR)
    print("App state loaded successfully")
    print(json.dumps(state["project_samples"], indent=2, ensure_ascii=False))
except Exception as e:
    import traceback
    traceback.print_exc()
