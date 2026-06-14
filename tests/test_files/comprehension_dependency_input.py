"""A module-level comprehension references a function eagerly, so it depends on it."""

placeholders = {name: build(name) for name in ["a", "b"]}


def build(name):
    """Used eagerly by the module-level comprehension above."""
    return f"value-{name}"


def lazy():
    """A comprehension here is deferred, so it imposes no ordering."""
    return [build(name) for name in ["c", "d"]]
