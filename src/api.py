"""
This module provides an API client for interacting with the Itau Uruguay bank system.
It includes functionality for logging in, retrieving account information, and fetching transactions.
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from ua_generator.options import Options

from .models import Account, Transaction, CreditCardTransaction
from .utils import b64decode, generate_headers, logger, BASE_URL, ERROR_CODES

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
        self.accounts: List[Account] = []
        self.credit_card_hash: str = ""

        # Default request values
        self._session = requests.Session()
        self._ua_options = Options(weighted_versions=True)
        self._headers = generate_headers()

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

    def get_accounts(self) -> List[Account]:
        """
        Returns the list of accounts
        :return: List of Account objects
        """
        return self.accounts

    def get_transactions(self, account: Account, start_date: str, end_date: str) -> List[Transaction]:
        """
        Returns transactions for a given account and date range
        :param account: Account object
        :param start_date: Start date in format "YYYY-MM-DD"
        :param end_date: End date in format "YYYY-MM-DD"
        :return: List of Transaction objects
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        transactions = []

        current_date = start
        while current_date <= end:
            month_transactions = self.get_month(account.id, current_date.month, current_date.year)
            transactions.extend([
                Transaction(
                    date=datetime.fromtimestamp(tx["fecha"]["millis"] / 1000).date(),
                    description=tx["descripcion"],
                    amount=tx["importe"],
                    balance=tx.get("saldo")
                )
                for tx in month_transactions
                if start_date <= datetime.fromtimestamp(tx["fecha"]["millis"] / 1000).strftime("%Y-%m-%d") <= end_date
            ])
            current_date = datetime(current_date.year + (current_date.month // 12), ((current_date.month % 12) + 1), 1)

        return transactions

    def get_credit_card_transactions(self) -> List[CreditCardTransaction]:
        """
        Returns the current credit card transactions
        :return: List of CreditCardTransaction objects
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Requesting credit card transactions")

        url = f"{BASE_URL}/tarjetas/credito/{self.credit_card_hash}/movimientos_actuales/00000000"
        response = self._session.get(url, headers=self._headers)
        response.raise_for_status()

        data = response.json()["itaulink_msg"]["data"]
        transactions = data.get("datos", {}).get("datosMovimientos", {}).get("movimientos", [])

        return [
            CreditCardTransaction(
                date=datetime.fromtimestamp(tx["fecha"]["millis"] / 1000).date(),
                description=tx["nombreComercio"],
                amount=tx["importe"],
                currency="Pesos" if tx["moneda"] == "Pesos" else "Dolares",
                current_installment=tx["nroCuota"],
                total_installments=tx["cantCuotas"]
            )
            for tx in transactions
        ]

    def get_month(self, account_hash: str, month: int, year: int) -> List[Dict[str, Any]]:
        """
        Returns transactions for a specific month and year
        :param account_hash: Account hash
        :param month: Month (1-12)
        :param year: Year (four-digit format)
        :return: List of transaction dictionaries
        """
        return self._download_month(account_hash, month, year % 100)

    def _do_login(self) -> requests.Response:
        """
        Performs the login request
        :return: Response object
        :raises requests.exceptions.RequestException: If there's a network error
        """
        url = f"{BASE_URL}/login"
        data = {
            "username": self._id,
            "password": self._pass,
            "submit": "Ingresar",
        }
        response = self._session.post(url, data=data, headers=self._headers, allow_redirects=False)
        response.raise_for_status()
        return response

    def _download_accounts(self) -> None:
        """
        Downloads trx and parses the accounts
        :raises Exception: If user data cannot be found or parsed
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Downloading trx")
        response = self._session.get(BASE_URL)
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
                self.accounts.append(Account(
                    id=account["idCuenta"],
                    name=f"{account['tipoCuenta']} - {account['nombreTitular']}",
                    balance=float(account["saldo"]),
                    currency=account["moneda"]
                ))
        logger.info("Parsed")

    def _get_credit_card_hash(self) -> str:
        """
        Fetches the credit card hash from the primerTarjeta endpoint
        :return: Credit card hash string
        :raises ValueError: If credit card hash cannot be fetched or parsed
        :raises requests.exceptions.RequestException: If there's a network error
        """
        logger.info("Fetching credit card hash")
        url = f"{BASE_URL}/tarjetas/credito/primerTarjeta"
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

    def _download_month(self, account_hash: str, month: int, year: int) -> List[Dict[str, Any]]:
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
            url = f"{BASE_URL}/cuentas/1/{account_hash}/mesActual"
            response = self._session.post(url, headers=self._headers)
            response.raise_for_status()
            data = response.json()["itaulink_msg"]["data"]
            return data["movimientosMesActual"]["movimientos"]
        elif month > current_month and year == current_year:
            raise ValueError("Future month")
        else:
            url = f"{BASE_URL}/cuentas/1/{account_hash}/{month}/{year}/consultaHistorica"
            response = self._session.post(url, headers=self._headers)
            response.raise_for_status()
            data = response.json()["itaulink_msg"]["data"]
            return data["mapaHistoricos"]["movimientosHistoricos"]["movimientos"]