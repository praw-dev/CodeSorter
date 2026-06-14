def Apple():
    """A public function whose name starts with a capital letter."""
    return None


def _helper():
    """A private function that should sort ahead of the public ones."""
    return None


def banana():
    """A public function whose name starts with a lowercase letter."""
    return None


class Widget:
    """Methods sort private-first as well."""

    def render(self):
        """Render the widget."""
        return None

    def _private(self):
        """A private helper."""
        return None

    def Build(self):
        """Build the widget."""
        return None


class _Base:
    """A private class that should sort ahead of the public ones."""

    def setup(self):
        """Set up the base."""
        return None
