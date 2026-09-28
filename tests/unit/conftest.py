# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path

# Make scripts/ importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
