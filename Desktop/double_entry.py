#!/usr/bin/env python3
"""
Simple Double-Entry Accounting Console App
- Uses Decimal for money
- Interactive menu to post transactions
- Supports equipment purchases, purchases on credit, wage accruals, sales on credit, bank loans, depreciation
- Produces T-accounts, Trial Balance, Income Statement, Balance Sheet
- All in standard library, single-file
"""

from dataclasses import dataclass, field
from decimal import Decimal, getcontext, ROUND_HALF_UP
from datetime import date
from typing import List, Dict, Tuple
import uuid
import sys

# ---------- Money helpers ----------
getcontext().prec = 28
CENT = Decimal('0.01')

def D(x) -> Decimal:
    # Convert to Decimal and quantize to cents
    if isinstance(x, Decimal):
        val = x
    else:
        val = Decimal(str(x))
    return val.quantize(CENT, rounding=ROUND_HALF_UP)

# ---------- Accounting domain ----------
@dataclass
class EntryLine:
    account: str
    amount: Decimal  # positive
    is_debit: bool

@dataclass
class JournalEntry:
    id: str
    date: date
    description: str
    lines: List[EntryLine]
    posted: bool = False

@dataclass
class Account:
    code: str
    name: str
    type: str  # 'Asset', 'Liability', 'Equity', 'Revenue', 'Expense'
    # For T-account view:
    debits: List[Tuple[str, Decimal]] = field(default_factory=list)   # list of (JE id, amount)
    credits: List[Tuple[str, Decimal]] = field(default_factory=list)

    def balance(self) -> Decimal:
        # compute balance respecting normal sign:
        total_debits = sum((amt for (_id, amt) in self.debits), D('0.00'))
        total_credits = sum((amt for (_id, amt) in self.credits), D('0.00'))
        # For presentation, we'll give numeric balance where:
        # asset & expense normal debit (positive balance means debit balance),
        # liability, equity, revenue normal credit (positive means credit balance).
        if self.type in ('Asset', 'Expense'):
            return total_debits - total_credits
        else:
            return total_credits - total_debits

# ---------- Ledger ----------
class Ledger:
    def __init__(self):
        self.accounts: Dict[str, Account] = {}
        self.journal: Dict[str, JournalEntry] = {}
        # Setup default accounts required by the user
        self._seed_accounts()

    def _seed_accounts(self):
        # codes are arbitrary but sorted in reporting
        for code, name, typ in [
            ('1000','Cash','Asset'),
            ('1010','Bank','Asset'),
            ('1020','Accounts Receivable','Asset'),
            ('1030','Inventory','Asset'),
            ('1040','Equipment','Asset'),
            ('1045','Accumulated Depreciation','Asset'),  # contra-asset shown as negative balance
            ('2000','Accounts Payable','Liability'),
            ('2100','Wages Payable','Liability'),
            ('2200','Bank Loan','Liability'),
            ('3000','Equity','Equity'),
            ('4000','Revenue','Revenue'),
            ('4100','Sales Returns','Revenue'),
            ('5000','COGS','Expense'),
            ('5100','Wages Expense','Expense'),
            ('5200','Rent & SG&A','Expense'),
            ('5300','Depreciation Expense','Expense'),
            ('5400','Interest Expense','Expense'),
            ('6000','Tax Expense','Expense'),
        ]:
            self.create_account(code, name, typ)

    def create_account(self, code: str, name: str, typ: str):
        if code in self.accounts:
            return
        self.accounts[code] = Account(code=code, name=name, type=typ)

    def get_account(self, code: str) -> Account:
        if code not in self.accounts:
            raise KeyError(f"Account {code} not defined")
        return self.accounts[code]

    def new_journal_entry(self, description: str, lines: List[EntryLine]) -> JournalEntry:
        # Validate: all amounts > 0 and balanced
        if any(l.amount <= 0 for l in lines):
            raise ValueError("All line amounts must be positive")
        deb = sum((l.amount for l in lines if l.is_debit), D('0.00'))
        cre = sum((l.amount for l in lines if not l.is_debit), D('0.00'))
        if deb != cre:
            raise ValueError(f"Journal entry unbalanced: debits {deb} != credits {cre}")
        je = JournalEntry(id=str(uuid.uuid4())[:8], date=date.today(), description=description, lines=lines)
        # store but not posted yet—posting will modify T-accounts
        self.journal[je.id] = je
        return je

    def post_entry(self, je_id: str):
        je = self.journal.get(je_id)
        if not je:
            raise KeyError("Journal entry not found")
        if je.posted:
            raise ValueError("Entry already posted")
        # apply lines to accounts
        for l in je.lines:
            acct = self.get_account(l.account)
            if l.is_debit:
                acct.debits.append((je.id, l.amount))
            else:
                acct.credits.append((je.id, l.amount))
        je.posted = True
        return je

    # convenience wrapper to create and post
    def post_transaction(self, description: str, lines: List[EntryLine]) -> JournalEntry:
        je = self.new_journal_entry(description, lines)
        self.post_entry(je.id)
        return je

    # Reports
    def t_accounts_report(self):
        out = []
        for code in sorted(self.accounts.keys()):
            acct = self.accounts[code]
            out.append((acct, acct.debits, acct.credits, acct.balance()))
        return out

    def trial_balance(self):
        rows = []
        for code in sorted(self.accounts.keys()):
            acct = self.accounts[code]
            bal = acct.balance()
            # Present Debit and Credit columns as absolute amounts
            if acct.type in ('Asset', 'Expense'):
                # normal debit
                if bal >= 0:
                    debit = bal
                    credit = D('0.00')
                else:
                    debit = D('0.00')
                    credit = -bal
            else:
                # normal credit (liability, equity, revenue)
                if bal >= 0:
                    credit = bal
                    debit = D('0.00')
                else:
                    credit = D('0.00')
                    debit = -bal
            rows.append({'code':code, 'name':acct.name, 'type':acct.type, 'debit':D(debit), 'credit':D(credit)})
        total_debit = sum((r['debit'] for r in rows), D('0.00'))
        total_credit = sum((r['credit'] for r in rows), D('0.00'))
        return rows, D(total_debit), D(total_credit)

    def balance_sheet(self):
        assets = []
        liabilities = []
        equity = []
        for acct in self.accounts.values():
            bal = acct.balance()
            if acct.type == 'Asset':
                assets.append((acct.code, acct.name, bal))
            elif acct.type == 'Liability':
                liabilities.append((acct.code, acct.name, bal))
            elif acct.type == 'Equity':
                equity.append((acct.code, acct.name, bal))
        return assets, liabilities, equity

    def income_statement(self):
        revenue = sum((self.accounts[a].balance() for a in self.accounts if self.accounts[a].type == 'Revenue'), D('0.00'))
        cogs = D('0.00')
        wages = D('0.00')
        sga = D('0.00')
        depreciation = D('0.00')
        interest = D('0.00')
        tax = D('0.00')
        for code, acct in self.accounts.items():
            if acct.type == 'Expense' and acct.name == 'COGS':
                cogs += acct.balance()
        # But our COGS account code is 5000; better iterate by code mapping
        # We'll compute by codes to be explicit:
        revenue = self.accounts['4000'].balance() if '4000' in self.accounts else D('0.00')
        cogs = self.accounts['5000'].balance() if '5000' in self.accounts else D('0.00')
        wages = self.accounts['5100'].balance() if '5100' in self.accounts else D('0.00')
        sga = self.accounts['5200'].balance() if '5200' in self.accounts else D('0.00')
        depreciation = self.accounts['5300'].balance() if '5300' in self.accounts else D('0.00')
        interest = self.accounts['5400'].balance() if '5400' in self.accounts else D('0.00')
        tax = self.accounts['6000'].balance() if '6000' in self.accounts else D('0.00')
        # Because balances follow the rule: Expense accounts' balance() returns debit > 0
        # Revenue returns credit positive (we defined that above)
        gross_profit = revenue - cogs
        sg_and_a = wages + sga
        ebit = gross_profit - sg_and_a - depreciation
        pre_tax = ebit - interest
        net_income = pre_tax - tax
        return {
            'revenue': D(revenue),
            'cogs': D(cogs),
            'gross_profit': D(gross_profit),
            'wages': D(wages),
            'sga': D(sga),
            'depreciation': D(depreciation),
            'ebit': D(ebit),
            'interest': D(interest),
            'tax': D(tax),
            'net_income': D(net_income)
        }

    # closing: move revenue and expense balances into Equity (Retained Earnings)
    def close_books(self):
        # Revenue (credit balances) -> debit revenue, credit equity
        # Expenses (debit balances) -> credit expense, debit equity
        total_revenue = D('0.00')
        total_expense = D('0.00')
        # Sum revenue (4000) and expenses (codes 5000-...)
        if '4000' in self.accounts:
            total_revenue = self.accounts['4000'].balance()
        for code, acct in self.accounts.items():
            if acct.type == 'Expense':
                total_expense += acct.balance()
        net_income = total_revenue - total_expense
        # Post clearing entries:
        # 1) Close revenue: debit revenue, credit equity
        if total_revenue != D('0.00'):
            self.post_transaction("Close Revenue", [
                EntryLine('4000', D(total_revenue), True),
                EntryLine('3000', D(total_revenue), False),
            ])
        # 2) Close each expense individually to Equity
        for code, acct in list(self.accounts.items()):
            if acct.type == 'Expense':
                amt = acct.balance()
                if amt != D('0.00'):
                    # debit equity, credit expense
                    self.post_transaction(f"Close Expense {acct.name}", [
                        EntryLine('3000', D(amt), True),
                        EntryLine(code, D(amt), False),
                    ])
        return D(net_income)

    # Depreciation: straight-line across 5 years (60 months) by default.
    def calculate_depreciation(self, equipment_account_code='1040', accum_depr_code='1045',
                               depr_expense_code='5300', months=1, life_years=5, salvage=Decimal('0.00')):
        """
        Calculate monthly depreciation for equipment and post depreciation expense and accumulated depreciation.
        months: number of months to depreciate (can be 1, or more)
        life_years: useful life in years (default 5)
        salvage: salvage value
        """
        equip = self.get_account(equipment_account_code)
        accum = self.get_account(accum_depr_code)
        # equipment total cost
        cost = equip.balance() if equip.type == 'Asset' else D('0.00')
        # Note: equipment balance is debit normal (asset). If user has negative etc, we'll just use debits - credits as balance()
        total_cost = cost
        # Compute monthly depreciation
        total_months = life_years * 12
        if total_months <= 0:
            raise ValueError("life_years must be > 0")
        depreciable = total_cost - D(salvage)
        if depreciable <= D('0.00'):
            return D('0.00')
        monthly = (depreciable / Decimal(total_months)).quantize(CENT, ROUND_HALF_UP)
        amt = monthly * months
        # Post depreciation: debit Depreciation Expense, credit Accumulated Depreciation
        if amt > D('0.00'):
            self.post_transaction(f"Depreciation for {months} month(s)", [
                EntryLine(depr_expense_code, D(amt), True),
                EntryLine(accum_depr_code, D(amt), False),
            ])
        return D(amt)

# ---------- Console UI helpers ----------
def fmt_money(x: Decimal) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"

def pause():
    input("\nPress Enter to continue...")

# ---------- Interactive app ----------
def print_menu():
    print("\n--- Simple Accounting App ---")
    print("1) Enter initial capital (owner investment)")
    print("2) Purchase equipment (cash or loan)")
    print("3) Purchase raw materials on credit (inventory/AP)")
    print("4) Accrue wages (wage payable/wage expense)")
    print("5) Make a sale on credit (AR / Revenue) and optionally record COGS & inventory movement")
    print("6) Receive cash from customer (AR / Cash)")
    print("7) Take a bank loan (cash / bank loan)")
    print("8) Record interest expense or payment")
    print("9) Calculate depreciation (straight-line, months)")
    print("10) Post a manual journal entry")
    print("11) Show T-accounts")
    print("12) Show Trial Balance")
    print("13) Show Income Statement")
    print("14) Show Balance Sheet")
    print("15) Close books (move revenues/expenses to Equity)")
    print("16) Demo scenario (sample transactions)")
    print("0) Exit")

def input_decimal(prompt: str) -> Decimal:
    while True:
        try:
            s = input(prompt + " ").strip()
            return D(Decimal(s))
        except Exception:
            print("Invalid amount. Try again (e.g. 1234.56)")

def run_app():
    ledger = Ledger()
    print("Welcome — this program records double-entry transactions and produces basic financial statements.")
    while True:
        print_menu()
        choice = input("\nChoose an option: ").strip()
        try:
            if choice == '1':
                amt = input_decimal("Enter initial capital amount (owner invests cash):")
                ledger.post_transaction("Owner investment - initial capital", [
                    EntryLine('1000', D(amt), True),   # Cash debit
                    EntryLine('3000', D(amt), False),  # Equity credit
                ])
                print("Posted owner investment.")
                pause()

            elif choice == '2':
                amt = input_decimal("Equipment purchase amount:")
                mode = input("Paid by (1) Cash or (2) Bank Loan? Enter 1 or 2: ").strip()
                if mode == '1':
                    # cash payment
                    ledger.post_transaction("Purchase equipment (cash)", [
                        EntryLine('1040', D(amt), True),  # Equipment debit
                        EntryLine('1000', D(amt), False), # Cash credit
                    ])
                else:
                    ledger.post_transaction("Purchase equipment (loan)", [
                        EntryLine('1040', D(amt), True),  # Equipment debit
                        EntryLine('2200', D(amt), False), # Bank Loan credit
                    ])
                print("Equipment purchase posted.")
                pause()

            elif choice == '3':
                amt = input_decimal("Raw material / inventory purchase amount (on credit):")
                ledger.post_transaction("Purchase raw materials on credit", [
                    EntryLine('1030', D(amt), True),   # Inventory debit
                    EntryLine('2000', D(amt), False),  # Accounts Payable credit
                ])
                print("Inventory/AP posted.")
                pause()

            elif choice == '4':
                amt = input_decimal("Wages to accrue (amount):")
                ledger.post_transaction("Accrue wages", [
                    EntryLine('5100', D(amt), True),   # Wages Expense debit
                    EntryLine('2100', D(amt), False),  # Wages Payable credit
                ])
                print("Wage accrual posted.")
                pause()

            elif choice == '5':
                amt = input_decimal("Sales amount (gross, invoice total):")
                cogs_amt = input_decimal("COGS amount for this sale (enter 0 if none):")
                # credit sale: AR (debit) / Revenue (credit)
                ledger.post_transaction("Sale on credit", [
                    EntryLine('1020', D(amt), True),   # Accounts Receivable debit
                    EntryLine('4000', D(amt), False),  # Revenue credit
                ])
                # COGS: debit COGS expense, credit inventory
                if cogs_amt > D('0.00'):
                    ledger.post_transaction("Record COGS and inventory reduction", [
                        EntryLine('5000', D(cogs_amt), True),  # COGS debit
                        EntryLine('1030', D(cogs_amt), False), # Inventory credit
                    ])
                print("Sale posted.")
                pause()

            elif choice == '6':
                amt = input_decimal("Cash received amount:")
                source = input("From (1) Customer (reduce AR) or (2) Other (just increase cash)? Enter 1 or 2: ").strip()
                if source == '1':
                    ledger.post_transaction("Cash received from customer", [
                        EntryLine('1000', D(amt), True),   # Cash debit
                        EntryLine('1020', D(amt), False),  # AR credit
                    ])
                else:
                    ledger.post_transaction("Cash receipt", [
                        EntryLine('1000', D(amt), True),
                        EntryLine('4000', D(amt), False),  # treat as revenue
                    ])
                print("Cash receipt posted.")
                pause()

            elif choice == '7':
                amt = input_decimal("Loan proceeds amount:")
                ledger.post_transaction("Bank loan taken", [
                    EntryLine('1000', D(amt), True),   # Cash debit
                    EntryLine('2200', D(amt), False),  # Bank Loan credit
                ])
                print("Loan posted.")
                pause()

            elif choice == '8':
                sub = input("Record (1) Interest expense accrual or (2) Interest payment? Enter 1 or 2: ").strip()
                amt = input_decimal("Interest amount:")
                if sub == '1':
                    ledger.post_transaction("Accrue interest expense", [
                        EntryLine('5400', D(amt), True),  # Interest expense debit
                        EntryLine('2200', D(amt), False), # increase liability (if capitalized) OR use payables - we'll credit loan for simplicity
                    ])
                else:
                    # interest payment: debit interest expense (if not already accrued) and credit cash
                    ledger.post_transaction("Interest payment", [
                        EntryLine('5400', D(amt), True),
                        EntryLine('1000', D(amt), False),
                    ])
                print("Interest recorded.")
                pause()

            elif choice == '9':
                months = int(input("Enter number of months to depreciate (e.g. 1): ").strip())
                amt = ledger.calculate_depreciation(months=months)
                print(f"Depreciation posted: {fmt_money(amt)}")
                pause()

            elif choice == '10':
                print("Manual journal entry. Enter lines until finished. The entry must balance.")
                desc = input("Description: ").strip()
                lines = []
                while True:
                    acc = input("Account code (e.g. 1000) or 'done': ").strip()
                    if acc.lower() == 'done':
                        break
                    if acc not in ledger.accounts:
                        print("Unknown account code. Available codes:")
                        for code, a in sorted(ledger.accounts.items()):
                            print(f"  {code} - {a.name}")
                        continue
                    amt = input_decimal("Amount:")
                    dc = input("Debit or Credit? (d/c): ").strip().lower()
                    is_debit = (dc == 'd')
                    lines.append(EntryLine(acc, D(amt), is_debit))
                if not lines:
                    print("No lines entered.")
                else:
                    try:
                        je = ledger.post_transaction(desc or "Manual JE", lines)
                        print(f"Posted JE {je.id}")
                    except Exception as e:
                        print("Failed to post entry:", e)
                pause()

            elif choice == '11':
                print("\n--- T-Accounts ---")
                for acct, debits, credits, bal in ledger.t_accounts_report():
                    print(f"\n{acct.code} {acct.name} ({acct.type})")
                    print("  Debits:")
                    for jid, amt in debits:
                        print(f"    {jid:8}  {fmt_money(amt)}")
                    print("  Credits:")
                    for jid, amt in credits:
                        print(f"    {jid:8}  {fmt_money(amt)}")
                    print(f"  Balance: {fmt_money(bal)}")
                pause()

            elif choice == '12':
                rows, td, tc = ledger.trial_balance()
                print("\n--- Trial Balance ---")
                print(f"{'Code':<6} {'Name':<25} {'Debit':>12} {'Credit':>12}")
                for r in rows:
                    print(f"{r['code']:<6} {r['name']:<25} {r['debit']:>12} {r['credit']:>12}")
                print("-"*60)
                print(f"{'Totals':<31} {td:>12} {tc:>12}")
                pause()

            elif choice == '13':
                isr = ledger.income_statement()
                print("\n--- Income Statement ---")
                print(f"Revenue:         {fmt_money(isr['revenue'])}")
                print(f"COGS:            {fmt_money(isr['cogs'])}")
                print(f"Gross Profit:    {fmt_money(isr['gross_profit'])}\n")
                print("Operating Expenses:")
                print(f"  Wages:         {fmt_money(isr['wages'])}")
                print(f"  SG&A:          {fmt_money(isr['sga'])}")
                print(f"  Depreciation:  {fmt_money(isr['depreciation'])}")
                print(f"EBIT:            {fmt_money(isr['ebit'])}")
                print(f"Interest:        {fmt_money(isr['interest'])}")
                print(f"Tax:             {fmt_money(isr['tax'])}")
                print(f"Net Income:      {fmt_money(isr['net_income'])}")
                pause()

            elif choice == '14':
                assets, liabilities, equity = ledger.balance_sheet()
                print("\n--- Balance Sheet ---")
                print("\nASSETS")
                total_assets = D('0.00')
                for code,name,bal in sorted(assets, key=lambda x: x[0]):
                    print(f"  {code} {name:<25} {fmt_money(bal)}")
                    total_assets += bal
                print(f"Total assets: {fmt_money(total_assets)}\n")
                print("LIABILITIES")
                total_liab = D('0.00')
                for code,name,bal in sorted(liabilities, key=lambda x: x[0]):
                    print(f"  {code} {name:<25} {fmt_money(bal)}")
                    total_liab += bal
                print(f"Total liabilities: {fmt_money(total_liab)}\n")
                print("EQUITY")
                total_equity = D('0.00')
                for code,name,bal in sorted(equity, key=lambda x: x[0]):
                    print(f"  {code} {name:<25} {fmt_money(bal)}")
                    total_equity += bal
                print(f"Total equity: {fmt_money(total_equity)}\n")
                print(f"Assets = {fmt_money(total_assets)}  Liabilities + Equity = {fmt_money(total_liab + total_equity)}")
                pause()

            elif choice == '15':
                net_inc = ledger.close_books()
                print(f"Books closed. Net income moved to Equity: {fmt_money(net_inc)}")
                pause()

            elif choice == '16':
                # Demo scenario: some sample transactions
                print("Running demo scenario...")
                # reset ledger fresh
                ledger = Ledger()
                ledger.post_transaction("Owner invests capital", [
                    EntryLine('1000', D('20000.00'), True),
                    EntryLine('3000', D('20000.00'), False),
                ])
                ledger.post_transaction("Buy equipment with cash", [
                    EntryLine('1040', D('8000.00'), True),
                    EntryLine('1000', D('8000.00'), False),
                ])
                ledger.post_transaction("Buy inventory on credit", [
                    EntryLine('1030', D('4000.00'), True),
                    EntryLine('2000', D('4000.00'), False),
                ])
                ledger.post_transaction("Take bank loan", [
                    EntryLine('1000', D('5000.00'), True),
                    EntryLine('2200', D('5000.00'), False),
                ])
                ledger.post_transaction("Accrue wages", [
                    EntryLine('5100', D('1200.00'), True),
                    EntryLine('2100', D('1200.00'), False),
                ])
                ledger.post_transaction("Sale on credit", [
                    EntryLine('1020', D('6000.00'), True),
                    EntryLine('4000', D('6000.00'), False),
                ])
                ledger.post_transaction("Record COGS", [
                    EntryLine('5000', D('2500.00'), True),
                    EntryLine('1030', D('2500.00'), False),
                ])
                ledger.calculate_depreciation(months=12)  # one year of depreciation
                print("Demo posted. Run reports to see results.")
                pause()

            elif choice == '0':
                print("Goodbye.")
                sys.exit(0)

            else:
                print("Unknown choice.")

        except Exception as e:
            print("Error:", e)
            pause()

if __name__ == '__main__':
    run_app()
