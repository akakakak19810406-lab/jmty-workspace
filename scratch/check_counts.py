import sys
import os
from pathlib import Path
import json

# Add scripts to path
sys.path.append(os.getcwd() + "/scripts")
import jmty_gui

ROOT = Path(os.getcwd())
DEFAULT_OUTPUT_ROOT = ROOT / "outputs/jmty-weekly/current"
DEFAULT_TEMPLATES_DIR = ROOT / "inputs/jmty_image_prompt_templates"

state = jmty_gui.app_state(DEFAULT_OUTPUT_ROOT, DEFAULT_TEMPLATES_DIR)
print(f"Number of accounts: {len(state['accounts'])}")
total_slots = sum(len(a['slots']) for a in state['accounts'])
print(f"Total slots: {total_slots}")
for a in state['accounts']:
    print(f"Account: {a['account_name']}, Slots: {list(a['slots'].keys())}")
