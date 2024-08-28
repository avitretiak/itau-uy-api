"""
This module contains tests for the Itau API client.
"""

import os
import logging
import pytest
from dotenv import load_dotenv
from src.api import ItauAPI
from src.models import Account, Transaction, CreditCardTransaction

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
    assert len(api.accounts) > 0, "Login failed: No accounts found"


def test_get_accounts(api: ItauAPI) -> None:
    api.login()
    accounts = api.accounts
    assert len(accounts) > 0, "No accounts found"
    for account in accounts:
        assert isinstance(account, Account), f"Account is not of type Account: {account}"
        assert account.id, "Account ID is missing"
        assert account.name, "Account name is missing"
        assert account.balance is not None, "Account balance is missing"
        assert account.currency, "Account currency is missing"


@pytest.mark.parametrize(
    "start_date, end_date",
    [
        ("2023-01-01", "2023-01-31"),
        ("2023-02-01", "2023-02-28"),
    ],
)
def test_get_transactions(api: ItauAPI, start_date: str, end_date: str) -> None:
    api.login()
    account = api.accounts[0]
    transactions = api.get_transactions(account, start_date, end_date)
    assert len(transactions) > 0, f"No transactions found between {start_date} and {end_date}"
    for tx in transactions:
        assert isinstance(tx, Transaction), f"Transaction is not of type Transaction: {tx}"
        assert tx.date, "Transaction date is missing"
        assert tx.type, "Transaction type is missing"
        assert tx.amount is not None, "Transaction amount is missing"
        assert tx.description, "Transaction description is missing"


def test_get_credit_card_transactions(api: ItauAPI) -> None:
    api.login()
    credit_transactions = api.get_credit_card_transactions()
    assert len(credit_transactions) > 0, "No credit card transactions found"
    for tx in credit_transactions:
        assert isinstance(
            tx, CreditCardTransaction
        ), f"Credit card transaction is not of type CreditCardTransaction: {tx}"
        assert tx.date, "Credit card transaction date is missing"
        assert tx.description, "Credit card transaction description is missing"
        assert tx.amount is not None, "Credit card transaction amount is missing"
        assert tx.currency, "Credit card transaction currency is missing"


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
            print(f"Account ID: {account.id}, Name: {account.name}, Balance: {account.balance} {account.currency}")
    except Exception as e:
        pytest.fail(f"Login failed: {str(e)}")
