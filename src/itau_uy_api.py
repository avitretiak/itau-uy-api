"""
This module provides an API client for interacting with the Itau Uruguay bank system.
It includes functionality for logging in, retrieving account information, and fetching transactions.
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
import ua_generator
from ua_generator.options import Options

from src.utils import b64decode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ERROR_CODES = {"10010": "Bad Login", "10020": "Bad Password"}


class ItauAPI:
    """
    Class that allows you to access your Itau account
    """

    def __init__(self, user_id: str, password: str):
        """
        Creates an ItauAPI object
        :param user_id: Your ID
        :param password: A base64 representation of your password
        :raises ValueError: If user_id or password is empty
        """
        if not user_id or not password:
            raise ValueError("User ID and password must not be empty")

        logger.info("Created new api for %s", user_id)
        self._id = user_id
        self._pass = b64decode(password)
        self.accounts: List[Dict[str, Any]] = []
        self.credit_card_hash: str = ""

        # Default request values
        self._base_url = "https://www.itaulink.com.uy/trx"
        self._session = requests.Session()
        self._ua_options = Options(weighted_versions=True)
        self._headers = self._generate_headers()

    def login(self) -> None:
        """
        Logins with the provided credentials
        :raises Exception: If login fails
        """
        logger.info("Logging in")
        response = self._do_login()

        redirect_url = response.headers.get("Location")
        if not redirect_url:
            print("No redirect URL found in response headers")
            raise ValueError("No redirect URL found after login attempt")

        redirect = urlparse(redirect_url)
        logger.info("Login redirected to %s", redirect.path)

        if redirect.path == "/trx/":
            self._download_accounts()
            self.credit_card_hash = self._get_credit_card_hash()
            logger.info("Credit card hash: %s", self.credit_card_hash)
            return

        query_params = parse_qs(redirect.query)
        code = query_params.get("message_code", [""])[0]
        code_message = ERROR_CODES.get(code, f"Unknown error (code: {code})")

        logger.error("Login failed! %s:%s", code, code_message)
        raise ValueError(f"Login failed: {code_message}")

    def get_month(self, account_hash: str, month: int, year: int) -> List[Dict[str, Any]]:
        """
        Returns the transactions for the given month
        :param account_hash: Account hash
        :param month: Month (1-12)
        :param year: Year (four-digit format)
        :return: List of transaction dictionaries
        :raises ValueError: If an invalid month or year is provided, or if a future month is requested
        :raises requests.exceptions.RequestException: If there's a network error
        """
        if not 1 <= month <= 12:
            raise ValueError("Month must be between 1 and 12")
        if year < 2000:
            raise ValueError("Year must be in four-digit format (e.g., 2023)")
        logger.info("Requesting movements for %s/%s", month, year)
        year = int(year)
        month = int(month)

        if year > 2000:
            year -= 2000

        movement_types = {
            "D": "expense",
            "C": "income",
        }

        try:
            movements = self._download_month(account_hash, month, year)
            return [
                {
                    "type": movement_types.get(movement["tipo"], "unknown"),
                    "description": movement["descripcion"],
                    "extraDescription": movement["descripcionAdicional"],
                    "amount": (-movement["importe"] if movement["tipo"] == "D" else movement["importe"]),
                    "endBalance": movement["saldo"],
                    "date": datetime.fromtimestamp(movement["fecha"]["millis"] / 1000),
                }
                for movement in movements
            ]
        except requests.exceptions.RequestException as e:
            if "expiredSession" in str(e):
                self.login()
                return self.get_month(account_hash, month, year)
            raise

    def _do_login(self) -> requests.Response:
        """
        Sends your login credentials.
        :return: Response object
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Sending credentials to /doLogin")
        headers = self._headers.copy()
        headers.update(
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.itau.com.uy",
                "Referer": "https://www.itau.com.uy/",
            }
        )
        response = self._session.post(
            f"{self._base_url}/doLogin",
            headers=headers,
            data={
                "tipo_documento": 1,
                "tipo_usuario": "R",
                "nro_documento": self._id,
                "pass": self._pass,
            },
            allow_redirects=False,
        )
        response.raise_for_status()
        return response

    def _download_accounts(self) -> None:
        """
        Downloads trx and parses the accounts
        :raises Exception: If user data cannot be found or parsed
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Downloading trx")
        response = self._session.get(self._base_url)
        response.raise_for_status()

        logger.info("Parsing trx")
        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", string=lambda t: t and "var mensajeUsuario = JSON.parse" in t)

        if not script_tag:
            raise ValueError("Could not find user data in the response")

        json_match = re.search(r"JSON\.parse\((\'|\")(.+?)\1\)", script_tag.string)
        if not json_match:
            raise ValueError("Could not extract JSON data from script")

        user_data = json.loads(json_match.group(2))
        logger.info("Parsed")

        logger.info("Parsing JSON")
        self.accounts = []
        for account_type in [
            "caja_de_ahorro",
            "cuenta_corriente",
            "cuenta_recaudadora",
            "cuenta_de_ahorro_junior",
        ]:
            for account in user_data["cuentas"].get(account_type, []):
                self.accounts.append(
                    {
                        "type": account["tipoCuenta"],
                        "id": account["idCuenta"],
                        "user": account["nombreTitular"],
                        "currency": account["moneda"],
                        "balance": account["saldo"],
                        "hash": account["hash"],
                        "customerHash": account["hashCustomer"],
                        "customer": account["customer"],
                    }
                )
        logger.info("Parsed")

    def _generate_headers(self) -> Dict[str, str]:
        """
        Generates headers using ua-generator
        :return: Dictionary of headers
        """
        ua = ua_generator.generate(device="desktop", browser=("chrome", "edge", "safari"), options=self._ua_options)
        headers: Dict[str, str] = ua.headers.get()
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",  # noqa: E501
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
            }
        )
        return headers

    def _get_credit_card_hash(self) -> str | Any:
        """
        Fetches the credit card hash from the primerTarjeta endpoint
        :return: Credit card hash string
        :raises ValueError: If credit card hash cannot be fetched or parsed
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Fetching credit card hash")
        url = f"{self._base_url}/tarjetas/credito/primerTarjeta"
        try:
            response = self._session.get(url, headers=self._headers, timeout=10)
            response.raise_for_status()
            logger.info("Response status code: %s", response.status_code)

            soup = BeautifulSoup(response.text, "html.parser")
            select_element = soup.find("select", id="tarjeta")

            if select_element:
                option = select_element.find("option", selected=True)
                if option:
                    value = option.get("value")
                    if value:
                        hash_part = value.split(":")[0]
                        return hash_part

            raise ValueError("Failed to parse credit card hash from response")
        except requests.exceptions.RequestException as e:
            logger.error("Network error while fetching credit card hash: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error while fetching credit card hash: %s", str(e))
            raise ValueError("Failed to fetch credit card hash") from e

    def get_credit_card_transactions(self) -> List[Dict[str, Any]]:
        """
        Returns the current credit card transactions
        :return: List of transaction dictionaries
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Requesting credit card transactions")

        url = f"{self._base_url}/tarjetas/credito/{self.credit_card_hash}/" "movimientos_actuales/00000000"
        response = self._session.get(url, headers=self._headers)
        response.raise_for_status()

        data = response.json()["itaulink_msg"]["data"]
        transactions = data.get("datos", {}).get("datosMovimientos", {}).get("movimientos", [])

        return [
            {
                "date": datetime.fromtimestamp(tx["fecha"]["millis"] / 1000),
                "description": tx["nombreComercio"],
                "extra_description": tx.get("descripcionAdicional"),
                "amount": tx["importe"],
                "currency": "Pesos" if tx["moneda"] == "Pesos" else "Dolares",
                "type": tx["tipo"],
                "installment_number": tx["nroCuota"],
                "total_installments": tx["cantCuotas"],
            }
            for tx in transactions
        ]

    def _download_month(self, account_hash: str, month: int, year: int) -> List[Dict[str, Any]] | Any:
        """
        Downloads raw movements
        :param account_hash: Account hash
        :param month: Month (1-12)
        :param year: Year (two-digit format)
        :return: List of movement dictionaries
        :raises ValueError: If a future month is requested
        :raises requests.exceptions.RequestException: If there's a network error
        """
        date = datetime.now()
        current_month = date.month
        current_year = date.year - 2000

        if month == current_month and year == current_year:
            url = f"{self._base_url}/cuentas/1/{account_hash}/mesActual"
            response = self._session.post(url, headers=self._headers)
            response.raise_for_status()
            data = response.json()["itaulink_msg"]["data"]
            return data["movimientosMesActual"]["movimientos"]
        elif month > current_month and year == current_year:
            raise ValueError("Future month")
        else:
            url = f"{self._base_url}/cuentas/1/{account_hash}/{month}/{year}/consultaHistorica"
            response = self._session.post(url, headers=self._headers)
            response.raise_for_status()
            data = response.json()["itaulink_msg"]["data"]
            return data["mapaHistoricos"]["movimientosHistoricos"]["movimientos"]
