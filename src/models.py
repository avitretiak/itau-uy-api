from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Account:
    id: str
    name: str
    balance: float
    currency: str

@dataclass
class Transaction:
    date: date
    description: str
    amount: float
    balance: Optional[float] = None

@dataclass
class CreditCardTransaction:
    date: date
    description: str
    amount: float
    currency: str
    current_installment: Optional[int] = None
    total_installments: Optional[int] = None