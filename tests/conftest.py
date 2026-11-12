"""Make `import src...` work when pytest is run from the project root.

These tests are fully offline: they import only src/tools.py, src/edges.py and
src/state.py. They never import src/nodes.py, so no OpenAI key is needed.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
