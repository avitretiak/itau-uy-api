"""
This module provides utility functions and constants for the Itau UY API.
"""

import base64
import logging
from typing import Dict
from ua_generator import generate
from ua_generator.options import Options

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.itaulink.com.uy/trx"
ERROR_CODES = {"10010": "Bad Login", "10020": "Bad Password"}

def b64decode(b64: str) -> str:
    """
    Decode a base64 encoded string.
    Args:
        b64 (str): The base64 encoded string to decode.
    Returns:
        str: The decoded ASCII string.
    """
    return base64.b64decode(b64).decode("ascii")

def generate_headers() -> Dict[str, str]:
    """
    Generates headers using ua-generator
    :return: Dictionary of headers
    """
    ua_options = Options(weighted_versions=True)
    ua = generate(device="desktop", browser=("chrome", "edge", "safari"), options=ua_options)
    headers: Dict[str, str] = ua.headers.get()
    headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "DNT": "1",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    })
    return headers