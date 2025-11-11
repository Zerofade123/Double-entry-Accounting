"""Models for the accounting system."""
from decimal import Decimal
from typing import Dict, List, Optional

# --- Account Types ---
ACCOUNT_TYPES = {
    "Asset": "debit",      # Natural balance is debit
    "Liability": "credit", # Natural balance is credit
    "Equity": "credit",    # Natural balance is credit
    "Revenue": "credit",   # Natural balance is credit
    "Expense": "debit"     # Natural balance is debit
}

class Account:
    """Represents an account in the double-entry accounting system."""
    
    def __init__(self, name: str, account_type: str):
        """Initialize an account.
        
        Args:
            name: Account name
            account_type: Type of account (Asset, Liability, etc.)
            
        Raises:
            ValueError: If account_type is invalid
        """
        if account_type not in ACCOUNT_TYPES:
            raise ValueError(
                f"Invalid account type: {account_type}. "
                f"Must be one of {', '.join(ACCOUNT_TYPES.keys())}"
            )
            
        self.name = name
        self.type = account_type
        self.debits: List[Decimal] = []
        self.credits: List[Decimal] = []

    def debit(self, amount: Decimal, description: str = "") -> None:
        """Record a debit entry.
        
        Args:
            amount: Amount to debit
            description: Optional description
        """
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        self.debits.append(amount)

    def credit(self, amount: Decimal, description: str = "") -> None:
        """Record a credit entry.
        
        Args:
            amount: Amount to credit
            description: Optional description
        """
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        self.credits.append(amount)

    @property
    def total_debit(self) -> Decimal:
        """Calculate total debits."""
        return sum(self.debits, Decimal('0'))

    @property
    def total_credit(self) -> Decimal:
        """Calculate total credits."""
        return sum(self.credits, Decimal('0'))

    @property
    def raw_balance(self) -> Decimal:
        """Calculate raw balance (debits - credits)."""
        return self.total_debit - self.total_credit

    @property
    def balance(self) -> Decimal:
        """Calculate account balance considering natural balance type.
        
        Returns:
            For asset and expense accounts:
                Positive balance = Debit balance (normal)
                Negative balance = Credit balance
                
            For liability, equity, and revenue accounts:
                Positive balance = Credit balance (normal)
                Negative balance = Debit balance
        """
        raw = self.raw_balance
        if ACCOUNT_TYPES[self.type] == "credit":
            return -raw  # Flip sign for natural credit accounts
        return raw

    def validate_transaction(self, is_debit: bool, amount: Decimal) -> None:
        """Validate a transaction for this account.
        
        Args:
            is_debit: Whether this is a debit entry
            amount: Transaction amount
            
        Raises:
            ValueError: If amount is invalid
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        # Future: Add specific validation rules per account type
        # For example, prevent negative cash balance