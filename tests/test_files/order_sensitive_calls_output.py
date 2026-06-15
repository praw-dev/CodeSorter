"""OrderedDict keeps its keyword-argument order; other calls and dict literals are sorted."""

import collections
from collections import OrderedDict


def build():
    """OrderedDict argument order is preserved; the regular call and dict literal are sorted."""
    ordered = OrderedDict(zeta=1, alpha=2, mu=3)
    qualified = collections.OrderedDict(zeta=1, alpha=2)
    regular = submit(alpha=2, zeta=1)
    literal = {"alpha": 2, "zeta": 1}
    return literal, ordered, qualified, regular
