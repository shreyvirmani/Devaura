from app.helpers import format_currency

def render_balance(account_name, balance):
    return f"{account_name}: {format_currency(balance)}"
