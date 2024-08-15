"""
This module contains tests for the Itau API client.
"""

import os
import logging
from datetime import datetime
import pytest
from dotenv import load_dotenv
from src.itau_uy_api import ItauAPI

load_dotenv()

# Set up logging
logging.basicConfig(
    filename="test_output.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


@pytest.fixture
def api() -> ItauAPI:
    user_id = os.environ.get("ITAU_USER_ID")
    password = os.environ.get("ITAU_PASSWORD")
    if not user_id or not password:
        pytest.skip("ITAU_USER_ID and ITAU_PASSWORD environment variables are required")
    api = ItauAPI(user_id, password)
    logging.info(f"Created API instance for user {user_id}")
    return api


def test_login(api: ItauAPI) -> None:
    api.login()
    assert len(api.accounts) > 0


def test_get_accounts(api: ItauAPI) -> None:
    api.login()
    for account in api.accounts:
        assert "type" in account
        assert "id" in account
        assert "balance" in account
        assert "currency" in account


def test_get_transactions(api: ItauAPI) -> None:
    api.login()

    current_month = datetime.now().month
    current_year = datetime.now().year
    transactions = api.get_month(api.accounts[0]["hash"], current_month, current_year)
    assert len(transactions) > 0
    for tx in transactions:
        assert "date" in tx
        assert "type" in tx
        assert "amount" in tx
        assert "description" in tx


def test_get_credit_card_transactions(api: ItauAPI) -> None:
    api.login()
    credit_transactions = api.get_credit_card_transactions()
    assert len(credit_transactions) > 0


def test_login_manual() -> None:
    # Get credentials from environment variables
    user_id = os.environ.get("ITAU_USER_ID")
    password = os.environ.get("ITAU_PASSWORD")

    if not user_id or not password:
        pytest.skip("ITAU_USER_ID and ITAU_PASSWORD environment variables are required")

    # Initialize the API
    api = ItauAPI(user_id, password)

    try:
        # Attempt to log in
        api.login()
        print("Login successful!")
        print(f"Number of accounts: {len(api.accounts)}")
        for account in api.accounts:
            print(
                f"Account type: {account['type']}, Balance: {account['balance']} {account['currency']}"
            )
    except Exception as e:
        pytest.fail(f"Login failed: {str(e)}")
