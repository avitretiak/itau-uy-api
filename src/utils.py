"""
This module provides utility functions for base64 encoding and decoding.
"""

import base64


def b64decode(b64: str) -> str:
    """
    Decode a base64 encoded string.
    Args:
        b64 (str): The base64 encoded string to decode.
    Returns:
        str: The decoded ASCII string.
    """
    return base64.b64decode(b64).decode("ascii")
