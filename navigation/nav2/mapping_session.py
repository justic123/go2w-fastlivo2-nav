"""A desktop estimator restart creates a new map even if capture keeps running."""
import json
from pathlib import Path
def current_mapping_run(root):
 root=Path(root)
 profile=root/'compute_location.json'
 if profile.exists() and json.loads(profile.read_text()).get('mode')=='desktop':
  return json.loads((root/'desktop_navigation.json').read_text())['session']
 return json.loads((root/'continuous_capture.json').read_text())['run']
