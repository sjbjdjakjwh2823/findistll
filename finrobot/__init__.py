import os
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
_vendor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "finrobot"))
if os.path.isdir(_vendor_path) and _vendor_path not in __path__:
    __path__.append(_vendor_path)
