import sys
from datetime import datetime

# Do not touch these. They use the local codesorter over the global codesorter.
sys.path.insert(0, ".")
sys.path.insert(1, "..")

from codesorter.const import __version__

always_use_bars_union = True
autodoc_typehints = "description"
copyright = datetime.today().strftime("%Y, Joel Payne")
exclude_patterns = ["_build"]
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
]
html_css_files = ["custom.css"]
html_static_path = ["_static"]
html_theme = "furo"
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
# libcst does not publish an intersphinx inventory, so its types cannot be resolved.
nitpick_ignore = [
    ("py:class", "CodemodContext"),
]
nitpicky = True
project = "codesorter"
release = __version__
version = ".".join(__version__.split(".", 2)[:2])
