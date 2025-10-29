#!/usr/bin/env python3
from app import create_app


def main():
    app = create_app()
    with app.app_context():
        from app.services.monthly_summary_service import MonthlySummaryService
        svc = MonthlySummaryService()
        print('Starting full rebuild of monthly summaries...')
        n = svc.rebuild_all()
        print(f'Rebuilt {n} months into monthly_summary table')


if __name__ == '__main__':
    main()
