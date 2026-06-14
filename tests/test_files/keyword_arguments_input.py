def alpha():
    """Keyword arguments, dict keys, and barriers are sorted within runs."""
    submit(selftext=body, title=title, flair_id=flair_id)
    nested(outer=inner(zeta=1, alpha=2), beta=3)
    config = {"title": title, "body": body, "flair": flair}
    call_spread(b=1, **extra, a=2)
    star_args(z=1, *args, c=3, a=2)
    dict_spread = {**base, "z": 1, "a": 2}
    return config, dict_spread, call_spread, star_args


def beta(self, *, title, selftext=None, flair_id=None):
    """Keyword-only parameters are sorted alphabetically."""
    return title
