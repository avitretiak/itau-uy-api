from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class TransactionType(Enum):
    """Enum representing the type of a transaction."""

    CREDIT = "C"
    DEBIT = "D"


class CCTransactionType(Enum):
    """Enum representing the type of a credit card transaction."""

    COMMON = "Comun"
    EMPTY = ""
    PAYMENT_PLAN = "Plan Pagos"


@dataclass
class Account:
    """Dataclass representing a bank account."""

    id: str
    hash: str
    name: str
    balance: float
    currency: str


@dataclass
class Transaction:
    """Dataclass representing a transaction."""

    date: date
    type: TransactionType
    description: str
    amount: float
    extraDescription: Optional[str] = None
    balance: Optional[float] = None


@dataclass
class CreditCardTransaction:
    """Dataclass representing a credit card transaction."""

    date: date
    description: str
    amount: float
    currency: str
    type: CCTransactionType
    current_installment: Optional[int] = None
    total_installments: Optional[int] = None
