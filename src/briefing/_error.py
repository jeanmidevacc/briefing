class BriefingError(Exception):
    """Raised for invalid input; the message says what to pass instead.

    Example::

        try:
            bf.Group("a", "b", columns=2, widths=[1])  # one width for two columns
        except bf.BriefingError as exc:
            print(exc)
    """
