def alpha():
    """Keyword arguments, dict keys, and barriers are sorted within runs."""
    submit(flair_id=flair_id, selftext=body, title=title)
    nested(beta=3, outer=inner(alpha=2, zeta=1))
    config = {"body": body, "flair": flair, "title": title}
    call_spread(a=2, b=1, **extra)
    star_args(z=1, *args, a=2, c=3)
    dict_spread = {**base, "a": 2, "z": 1}
    return config, dict_spread, call_spread, star_args


def beta(self, *, flair_id=None, selftext=None, title):
    """Keyword-only parameters are sorted alphabetically."""
    return title
