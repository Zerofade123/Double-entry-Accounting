from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
import storage

app = FastAPI(title="Double Entry Accounting System")
templates = Jinja2Templates(directory="templates")

# --- Account Categories and Types ---
ACCOUNT_CATEGORIES = {
    "Assets": ["Current Assets", "Fixed Assets", "Other Assets"],
    "Liabilities": ["Current Liabilities", "Long Term Liabilities"],
    "Equity": ["Owner's Equity", "Retained Earnings"],
    "Revenue": ["Operating Revenue", "Other Revenue"],
    "Expenses": ["Operating Expenses", "Other Expenses"]
}

ACCOUNT_TYPES = {
    "Asset": "debit",  # Natural balance: debit
    "Liability": "credit",
    "Equity": "credit",
    "Revenue": "credit",
    "Expense": "debit"
}

# --- Accounting data structures ---
class Account:
    def __init__(self, name: str, account_type: str, category: str):
        """Initialize an account with name, type and category.
        
        Args:
            name: Account name
            account_type: One of Asset, Liability, Equity, Revenue, Expense
            category: Subcategory within the account type (e.g. "Current Assets")
        """
        if account_type not in ACCOUNT_TYPES:
            raise ValueError(f"Invalid account type: {account_type}")
        
        self.name = name
        self.type = account_type
        self.category = category
        self.debits = []  # List of {"amount": Decimal, "date": date, "description": str}
        self.credits = [] # List of {"amount": Decimal, "date": date, "description": str}
        self.created_at = date.today()

    def debit(self, amount: Decimal, description: str = "", when: Optional[date] = None) -> None:
        """Record a debit entry with amount, description and date."""
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        self.debits.append({
            "amount": amount,
            "description": description,
            "date": when or date.today()
        })

    def credit(self, amount: Decimal, description: str = "", when: Optional[date] = None) -> None:
        """Record a credit entry with amount, description and date."""
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
            
        self.credits.append({
            "amount": amount,
            "description": description,
            "date": when or date.today()
        })

    @property
    def total_debit(self) -> Decimal:
        """Calculate total debits."""
        return sum(entry["amount"] for entry in self.debits)

    @property
    def total_credit(self) -> Decimal:
        """Calculate total credits."""
        return sum(entry["amount"] for entry in self.credits)

    @property
    def balance(self) -> Decimal:
        """Calculate balance according to account type's natural balance."""
        raw_balance = self.total_debit - self.total_credit
        
        # For liability, equity, and revenue accounts, invert the sign
        # so positive numbers represent their natural state
        if ACCOUNT_TYPES[self.type] == "credit":
            return -raw_balance
        return raw_balance

    @property
    def entries(self) -> List[Dict]:
        """Return all entries sorted by date for account statement."""
        all_entries = []
        
        # Add debit entries
        for entry in self.debits:
            all_entries.append({
                "date": entry["date"],
                "description": entry["description"],
                "debit": entry["amount"],
                "credit": Decimal("0"),
                "type": "debit"
            })
            
        # Add credit entries
        for entry in self.credits:
            all_entries.append({
                "date": entry["date"],
                "description": entry["description"],
                "debit": Decimal("0"),
                "credit": entry["amount"],
                "type": "credit"
            })
            
        # Sort by date
        return sorted(all_entries, key=lambda x: x["date"])

    def statement(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict]:
        """Generate account statement for date range with running balance."""
        entries = self.entries
        if start_date:
            entries = [e for e in entries if e["date"] >= start_date]
        if end_date:
            entries = [e for e in entries if e["date"] <= end_date]
            
        # Calculate running balance
        balance = Decimal("0")
        statement = []
        
        for entry in entries:
            if ACCOUNT_TYPES[self.type] == "credit":
                # For liability/equity/revenue, credits increase balance
                balance += entry["credit"] - entry["debit"]
            else:
                # For assets/expenses, debits increase balance
                balance += entry["debit"] - entry["credit"]
                
            statement.append({
                **entry,
                "balance": balance
            })
            
        return statement

# --- Initial Chart of Accounts ---
INITIAL_ACCOUNTS = {
    # Asset accounts
    "Cash": ("Asset", "Current Assets"),
    "Accounts Receivable": ("Asset", "Current Assets"),
    "Inventory": ("Asset", "Current Assets"),
    "Equipment": ("Asset", "Fixed Assets"),
    "Accumulated Depreciation": ("Asset", "Fixed Assets"),
    
    # Liability accounts
    "Accounts Payable": ("Liability", "Current Liabilities"),
    "Wages Payable": ("Liability", "Current Liabilities"),
    "Bank Loan": ("Liability", "Long Term Liabilities"),
    
    # Equity accounts
    "Owner's Equity": ("Equity", "Owner's Equity"),
    "Retained Earnings": ("Equity", "Retained Earnings"),
    
    # Revenue accounts
    "Sales Revenue": ("Revenue", "Operating Revenue"),
    "Service Revenue": ("Revenue", "Operating Revenue"),
    "Interest Income": ("Revenue", "Other Revenue"),
    
    # Expense accounts
    "Cost of Goods Sold": ("Expense", "Operating Expenses"),
    "Salary Expense": ("Expense", "Operating Expenses"),
    "Rent Expense": ("Expense", "Operating Expenses"),
    "Utilities Expense": ("Expense", "Operating Expenses"),
    "Depreciation Expense": ("Expense", "Operating Expenses"),
    "Interest Expense": ("Expense", "Other Expenses")
}

# Load saved data or initialize with defaults
accounts, transactions = storage.load_data()

if not accounts:  # First run, initialize with default accounts
    accounts = {
        name: Account(name, type_, category)
        for name, (type_, category) in INITIAL_ACCOUNTS.items()
    }
    transactions = []


# --- Helper functions ---
def validate_transaction(debits: Dict[str, Decimal], credits: Dict[str, Decimal]) -> None:
    """Validate transaction entries."""
    if not debits or not credits:
        raise ValueError("Both debit and credit entries are required")
        
    total_debit = sum(debits.values())
    total_credit = sum(credits.values())
    
    if total_debit != total_credit:
        raise ValueError(
            f"Transaction not balanced: debits ({total_debit}) ≠ credits ({total_credit})"
        )

def post_transaction(
    debits: Dict[str, Decimal],
    credits: Dict[str, Decimal],
    description: str,
    transaction_date: Optional[date] = None
) -> Dict:
    """Post a transaction to the ledger.
    
    Args:
        debits: Dict mapping account names to debit amounts
        credits: Dict mapping account names to credit amounts
        description: Transaction description
        transaction_date: Optional transaction date (defaults to today)
    
    Returns:
        Dict containing the posted transaction details
    
    Raises:
        ValueError: If transaction is invalid
        KeyError: If an account doesn't exist
    """
    validate_transaction(debits, credits)
    
    # Get or create date
    tx_date = transaction_date or date.today()
    
    # Apply entries to accounts
    try:
        for acct, amt in debits.items():
            accounts[acct].debit(amt, description, tx_date)
        for acct, amt in credits.items():
            accounts[acct].credit(amt, description, tx_date)
    except KeyError as e:
        raise ValueError(f"Account not found: {str(e)}")
        
    # Record transaction in history
    tx = {
        "id": len(transactions) + 1,
        "date": tx_date,
        "description": description,
        "amount": sum(debits.values()),
        "debit_entries": [{"account": k, "amount": v} for k, v in debits.items()],
        "credit_entries": [{"account": k, "amount": v} for k, v in credits.items()],
    }
    transactions.insert(0, tx)  # newest first
    
    # Persist data
    storage.save_data(accounts, transactions)
    
    return tx

def calculate_depreciation(as_of_date: Optional[date] = None) -> None:
    """Calculate and record depreciation entries.
    
    Uses straight-line depreciation with:
    - Equipment: 5 year life
    - Buildings: 27.5 year life
    """
    entry_date = as_of_date or date.today()
    
    # Equipment depreciation (5 year straight-line)
    equipment_cost = accounts["Equipment"].balance
    annual_depreciation = (equipment_cost / Decimal("5.0")).quantize(Decimal("0.01"))
    monthly_depreciation = (annual_depreciation / Decimal("12.0")).quantize(Decimal("0.01"))
    
    description = f"Monthly depreciation for {entry_date.strftime('%B %Y')}"
    accounts["Depreciation Expense"].debit(monthly_depreciation, description, entry_date)
    accounts["Accumulated Depreciation"].credit(monthly_depreciation, description, entry_date)

def get_accounts_by_type(account_type: str) -> Dict[str, Account]:
    """Get all accounts of a specific type."""
    return {
        name: account for name, account in accounts.items()
        if account.type == account_type
    }

def trial_balance(as_of_date: Optional[date] = None) -> Dict:
    """Generate trial balance as of specified date."""
    # Group accounts by type
    trial_data = {"accounts": [], "totals": {}}
    
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    
    for account in sorted(accounts.values(), key=lambda x: (x.type, x.name)):
        # Get balances up to as_of_date if specified
        if as_of_date:
            entries = account.statement(end_date=as_of_date)
            balance = entries[-1]["balance"] if entries else Decimal("0")
        else:
            balance = account.balance
            
        # Determine debit/credit presentation based on natural balance
        debit_amt = balance if balance > 0 else Decimal("0")
        credit_amt = -balance if balance < 0 else Decimal("0")
        
        if ACCOUNT_TYPES[account.type] == "credit":
            # Flip presentation for natural credit accounts
            debit_amt, credit_amt = credit_amt, debit_amt
            
        trial_data["accounts"].append({
            "name": account.name,
            "type": account.type,
            "category": account.category,
            "debit": debit_amt,
            "credit": credit_amt
        })
        
        total_debits += debit_amt
        total_credits += credit_amt
    
    trial_data["totals"] = {
        "total_debits": total_debits,
        "total_credits": total_credits,
        "is_balanced": total_debits == total_credits
    }
    
    return trial_data

def income_statement(start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict:
    """Generate income statement for the specified period."""
    # Initialize sections
    operating_revenue = Decimal("0")
    other_revenue = Decimal("0")
    operating_expenses = Decimal("0")
    other_expenses = Decimal("0")
    
    # Categorize and sum entries
    for account in accounts.values():
        if account.type == "Revenue":
            entries = account.statement(start_date, end_date)
            balance = entries[-1]["balance"] if entries else Decimal("0")
            
            if account.category == "Operating Revenue":
                operating_revenue += balance
            else:
                other_revenue += balance
                
        elif account.type == "Expense":
            entries = account.statement(start_date, end_date)
            balance = entries[-1]["balance"] if entries else Decimal("0")
            
            if account.category == "Operating Expenses":
                operating_expenses += balance
            else:
                other_expenses += balance
    
    # Calculate key metrics
    total_revenue = operating_revenue + other_revenue
    total_expenses = operating_expenses + other_expenses
    operating_income = operating_revenue - operating_expenses
    net_income = total_revenue - total_expenses
    
    return {
        "period": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None
        },
        "operating": {
            "revenue": operating_revenue,
            "expenses": operating_expenses,
            "income": operating_income
        },
        "other": {
            "revenue": other_revenue,
            "expenses": other_expenses
        },
        "totals": {
            "revenue": total_revenue,
            "expenses": total_expenses,
            "net_income": net_income
        },
        "detail": {
            "revenue": [
                {
                    "account": acc.name,
                    "category": acc.category,
                    "amount": acc.statement(start_date, end_date)[-1]["balance"] if acc.statement(start_date, end_date) else Decimal("0")
                }
                for acc in accounts.values()
                if acc.type == "Revenue"
            ],
            "expenses": [
                {
                    "account": acc.name,
                    "category": acc.category,
                    "amount": acc.statement(start_date, end_date)[-1]["balance"] if acc.statement(start_date, end_date) else Decimal("0")
                }
                for acc in accounts.values()
                if acc.type == "Expense"
            ]
        }
    }

def balance_sheet(as_of_date: Optional[date] = None) -> Dict:
    """Generate balance sheet as of specified date."""
    # Initialize sections
    assets = {"Current Assets": [], "Fixed Assets": [], "Other Assets": []}
    liabilities = {"Current Liabilities": [], "Long Term Liabilities": []}
    equity = {"Owner's Equity": [], "Retained Earnings": []}
    
    # Categorize accounts and get balances
    for account in accounts.values():
        if as_of_date:
            entries = account.statement(end_date=as_of_date)
            balance = entries[-1]["balance"] if entries else Decimal("0")
        else:
            balance = account.balance
            
        entry = {"name": account.name, "balance": balance}
        
        if account.type == "Asset":
            assets[account.category].append(entry)
        elif account.type == "Liability":
            liabilities[account.category].append(entry)
        elif account.type == "Equity":
            equity[account.category].append(entry)
    
    # Calculate totals
    total_assets = sum(
        entry["balance"]
        for section in assets.values()
        for entry in section
    )
    
    total_liabilities = sum(
        entry["balance"]
        for section in liabilities.values()
        for entry in section
    )
    
    total_equity = sum(
        entry["balance"]
        for section in equity.values()
        for entry in section
    )
    
    # Get retained earnings from income statement
    if as_of_date:
        net_income = income_statement(end_date=as_of_date)["totals"]["net_income"]
    else:
        net_income = income_statement()["totals"]["net_income"]
    
    return {
        "as_of_date": as_of_date.isoformat() if as_of_date else date.today().isoformat(),
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "totals": {
            "assets": total_assets,
            "liabilities": total_liabilities,
            "equity": total_equity + net_income,
            "liabilities_and_equity": total_liabilities + total_equity + net_income
        },
        "is_balanced": total_assets == (total_liabilities + total_equity + net_income)
    }

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request, 
            "accounts": accounts, 
            "transactions": transactions,
            "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
            "form_data": None
        },
    )

@app.post("/transaction")
async def transaction(
    request: Request,
    description: str = Form(...),
    debit_account: str = Form(...),
    credit_account: str = Form(...),
    amount: float = Form(...),
):
    # Store form data for persistence on error
    form_data = {
        "description": description,
        "debit_account": debit_account,
        "credit_account": credit_account,
        "amount": amount
    }
    
    # Validation
    if not description.strip():
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "accounts": accounts,
                "transactions": transactions,
                "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
                "error": "Description cannot be empty",
                "form_data": form_data
            }
        )
        
    if debit_account not in accounts:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "accounts": accounts,
                "transactions": transactions,
                "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
                "error": f"Invalid debit account: {debit_account}",
                "form_data": form_data
            }
        )
        
    if credit_account not in accounts:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "accounts": accounts,
                "transactions": transactions,
                "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
                "error": f"Invalid credit account: {credit_account}",
                "form_data": form_data
            }
        )
        
    if debit_account == credit_account:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "accounts": accounts,
                "transactions": transactions,
                "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
                "error": "Debit and credit accounts must be different",
                "form_data": form_data
            }
        )
        
    if amount <= 0:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "accounts": accounts,
                "transactions": transactions,
                "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
                "error": "Amount must be positive",
                "form_data": form_data
            }
        )
        
    try:
        # Convert amount to Decimal for precise calculations
        amt = Decimal(str(amount))
        post_transaction({debit_account: amt}, {credit_account: amt}, description)
        return RedirectResponse("/", status_code=303)
        
    except ValueError as e:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "accounts": accounts,
                "transactions": transactions,
                "ACCOUNT_CATEGORIES": ACCOUNT_CATEGORIES,
                "error": str(e),
                "form_data": form_data
            }
        )

@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    calculate_depreciation()
    tb = trial_balance()
    isr = income_statement()
    bs = balance_sheet()
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "trial": tb, "isr": isr, "bs": bs},
    )
