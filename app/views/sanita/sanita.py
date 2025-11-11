"""Pagine relative alla sezione Sanità (Terapia Biologica)."""
from flask import Blueprint, render_template, request, current_app, jsonify
from datetime import date, timedelta
from app import db
from app.models.Terapia import TerapiaPlan, TerapiaDelivery

sanita_bp = Blueprint('sanita', __name__)


@sanita_bp.route('/terapia')
def terapia():
    """Pagina Terapia Biologica: mostra calendario annuale e strumenti per gestire le forniture."""
    try:
        today = date.today()
        current_year = today.year
        next_year = current_year + 1
        return render_template('sanita/terapia_biologica.html', current_year=current_year, next_year=next_year)
    except Exception:
        current_app.logger.exception('Errore render terapia biologica')
        return render_template('sanita/terapia_biologica.html', current_year=date.today().year, next_year=date.today().year + 1)


def add_months(dt, months):
    """Add months to a date handling month overflow (naive implementation)."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, (date(year, month % 12 + 1, 1) - timedelta(days=1)).day)
    return date(year, month, day)


@sanita_bp.route('/api/plan', methods=['GET'])
def get_plan():
    """Return latest terapia plan if any."""
    try:
        plan = TerapiaPlan.query.order_by(TerapiaPlan.id.desc()).first()
        if not plan:
            return jsonify({'plan': None})
        return jsonify({'plan': plan.to_dict()})
    except Exception:
        current_app.logger.exception('Errore retrieving plan')
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/plan', methods=['POST'])
def save_plan():
    """Create a new plan and deliveries. Expected JSON: start_date (YYYY-MM-DD), total_drugs
    Number of deliveries is computed server-side as total_drugs // 2 (2 drugs per delivery).
    """
    data = request.get_json() or {}
    try:
        sd = data.get('start_date')
        total = int(data.get('total_drugs') or 0)
        # number of deliveries is computed as total_drugs // 2 (one delivery contains 2 drugs)
        num = int(total // 2)
        if not sd or total <= 0 or num <= 0:
            return jsonify({'error': 'invalid'}), 400
        parts = sd.split('-')
        start = date(int(parts[0]), int(parts[1]), int(parts[2]))

        # ensure tables exist
        db.create_all()
        plan = TerapiaPlan(start_date=start, total_drugs=total, num_deliveries=num)
        db.session.add(plan)
        db.session.flush()

        # Each delivery is monthly starting from start, quantity fixed at 2 (per spec)
        qty_per_delivery = 2
        cur_date = start
        # Prepare map of received flags if provided by client
        provided_deliveries = {}
        for pd in data.get('deliveries', []) or []:
            dd = pd.get('delivery_date')
            if dd:
                provided_deliveries[dd] = bool(pd.get('received'))

        for i in range(num):
            d = TerapiaDelivery(plan_id=plan.id, delivery_date=cur_date, quantity=qty_per_delivery, received=False)
            # if client provided received flag for this date, apply it
            iso = cur_date.isoformat()
            if iso in provided_deliveries and provided_deliveries[iso]:
                d.received = True
            db.session.add(d)
            # next month
            cur_date = add_months(cur_date, 1)

        db.session.commit()
        return jsonify({'plan': plan.to_dict()})
    except Exception:
        current_app.logger.exception('Errore saving plan')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/delivery/<int:did>/toggle', methods=['POST'])
def toggle_delivery(did):
    try:
        delivery = TerapiaDelivery.query.get(did)
        if not delivery:
            return jsonify({'error': 'not_found'}), 404
        delivery.received = not bool(delivery.received)
        db.session.add(delivery)
        db.session.commit()
        return jsonify({'delivery': delivery.to_dict()})
    except Exception:
        current_app.logger.exception('Errore toggling delivery')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/plan', methods=['DELETE'])
def delete_plan():
    """Delete the latest terapia plan and its deliveries."""
    try:
        plan = TerapiaPlan.query.order_by(TerapiaPlan.id.desc()).first()
        if not plan:
            return jsonify({'result': 'none'}), 200
        # delete cascade will remove deliveries
        db.session.delete(plan)
        db.session.commit()
        return jsonify({'result': 'deleted'})
    except Exception:
        current_app.logger.exception('Errore deleting plan')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500

