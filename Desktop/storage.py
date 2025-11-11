"""Storage module for persisting accounting data."""
import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

DATA_FILE = "accounting_data.json"
BACKUP_DIR = "backups"

class DataEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal and dates."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

def save_data(accounts: Dict, transactions: List) -> None:
    """Save accounts and transactions to JSON file with backup."""
    # Ensure backup directory exists
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Create backup of existing data if any
    if os.path.exists(DATA_FILE):
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.rename(DATA_FILE, os.path.join(BACKUP_DIR, backup_name))
    
    # Save current data
    data = {
        "accounts": {
            name: {
                "name": acc.name,
                "type": acc.type,
                "category": acc.category,
                "debits": [
                    {"amount": e["amount"], "date": e["date"].isoformat(), 
                     "description": e["description"]}
                    for e in acc.debits
                ],
                "credits": [
                    {"amount": e["amount"], "date": e["date"].isoformat(),
                     "description": e["description"]}
                    for e in acc.credits
                ]
            }
            for name, acc in accounts.items()
        },
        "transactions": transactions
    }
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, cls=DataEncoder, indent=2)

def load_data() -> tuple:
    """Load accounts and transactions from JSON file."""
    if not os.path.exists(DATA_FILE):
        return {}, []
        
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
            
        # Reconstruct accounts
        from app import Account  # local import to avoid circular dependency
        accounts = {}
        for name, acc_data in data["accounts"].items():
            account = Account(acc_data["name"], acc_data["type"], acc_data["category"])
            for entry in acc_data["debits"]:
                account.debit(
                    Decimal(entry["amount"]),
                    entry["description"],
                    datetime.fromisoformat(entry["date"]).date()
                )
            for entry in acc_data["credits"]:
                account.credit(
                    Decimal(entry["amount"]),
                    entry["description"],
                    datetime.fromisoformat(entry["date"]).date()
                )
            accounts[name] = account
            
        # Load transactions
        transactions = data["transactions"]
        # Convert amounts back to Decimal
        for tx in transactions:
            tx["amount"] = Decimal(tx["amount"])
            tx["date"] = datetime.fromisoformat(tx["date"]).date()
            
        return accounts, transactions
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error loading data: {e}")
        # If loading fails, return empty data
        return {}, []