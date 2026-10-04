"""Import the same standalone helper that bootstrap copies into generated projects."""
import importlib.util
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("noetloom_project_helper", KIT_ROOT / ".noetloom/project.py")
helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)
