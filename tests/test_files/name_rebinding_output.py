"""An assignment that rebinds a method name stays after the method it wraps."""


class Klass:
    def alpha(self):
        """A method that sorts first alphabetically."""
        return 1

    def beta(self):
        """A plain method."""
        return 2

    def ten(self):
        return 10

    ten = cachedproperty(ten, doc="Return 10.")
