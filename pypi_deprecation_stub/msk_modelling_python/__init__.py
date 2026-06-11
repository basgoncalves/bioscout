import warnings
warnings.warn(
    "msk-modelling-python has been renamed to bioscout. "
    "Please update your code: pip install bioscout",
    DeprecationWarning,
    stacklevel=2,
)
# Re-export everything from bioscout so existing imports don't break immediately
from bioscout import *  # noqa: F401, F403
