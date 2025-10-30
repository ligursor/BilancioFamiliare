"""Script di utilità per rigenerare le generated_transaction dalle ricorrenze.

Esegue la popolazione per i prossimi 6 mesi a partire dal periodo corrente.
"""
from app import create_app

app = create_app()

with app.app_context():
	from app.services.generated_transaction_service import GeneratedTransactionService
	svc = GeneratedTransactionService()
	created = svc.populate_horizon_from_recurring(months=6)
	print(f"GeneratedTransaction create: {created}")
