"""Run: python -m barter [path/to/community.json]"""

import os
import sys

from .explain import explain
from .matcher import match
from .models import load_community

DEFAULT = os.path.join(os.path.dirname(__file__), "..", "data", "maple_commons.json")


def main(argv):
    path = argv[1] if len(argv) > 1 else DEFAULT
    community = load_community(path)
    print(f"{len(community.participants)} participants · synthetic data\n")
    print(explain(match(community)))


if __name__ == "__main__":
    main(sys.argv)
