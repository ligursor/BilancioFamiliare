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


@sanita_bp.route('/api/plan', methods=['GET'])
def get_plan():
    """Return the single active terapia plan if any."""
    try:
        plan = TerapiaPlan.query.first()
        if not plan:
            return jsonify({'plan': None})
        return jsonify({'plan': plan.to_dict()})
    except Exception:
        current_app.logger.exception('Errore retrieving plan')
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/plan', methods=['POST'])
def save_plan():
    """Create a new plan with all deliveries in one operation.
    Only one plan can exist at a time.
    If a plan already exists, return error - user must delete first.
    Expected JSON: start_date (YYYY-MM-DD), total_drugs
    Creates all deliveries with progressive numbers, first one marked as received.
    """
    data = request.get_json() or {}
    try:
        # Check if a plan already exists
        existing = TerapiaPlan.query.first()
        if existing:
            return jsonify({'error': 'plan_exists', 'message': 'Esiste già un piano. Eliminarlo prima di crearne uno nuovo.'}), 400
        
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
        
        # Create plan
        plan = TerapiaPlan(start_date=start, total_drugs=total, num_deliveries=num)
        db.session.add(plan)
        db.session.flush()

        # Create ALL deliveries by date: every 28 days from start until end of next year
        qty_per_delivery = 2
        cur = start
        end_year = start.year + 1
        last_day = date(end_year, 12, 31)
        delivery_num = 0
        while cur <= last_day:
            delivery_num += 1
            # Mark the first delivery as received
            is_received = True if delivery_num == 1 else False
            d = TerapiaDelivery(
                plan_id=plan.id,
                delivery_number=delivery_num,
                quantity=qty_per_delivery,
                received=is_received
            )
            db.session.add(d)
            # advance 28 days
            cur = cur + timedelta(days=28)

        # Update plan totals based on created deliveries
        plan.num_deliveries = delivery_num
        plan.total_drugs = plan.num_deliveries * qty_per_delivery

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
        # Return the full plan to update UI
        plan = TerapiaPlan.query.get(delivery.plan_id)
        return jsonify({'plan': plan.to_dict() if plan else None})
    except Exception:
        current_app.logger.exception('Errore toggling delivery')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/delivery/next/mark', methods=['POST'])
def mark_next_delivery():
    """Mark the first unreceived delivery of the active plan as received and return updated plan."""
    try:
        plan = TerapiaPlan.query.first()
        if not plan:
            return jsonify({'error': 'no_plan'}), 404
        delivery = TerapiaDelivery.query.filter_by(plan_id=plan.id, received=False).order_by(TerapiaDelivery.delivery_number).first()
        if not delivery:
            return jsonify({'error': 'no_pending'}), 400
        delivery.received = True
        db.session.add(delivery)
        db.session.commit()
        plan = TerapiaPlan.query.get(plan.id)
        return jsonify({'plan': plan.to_dict()})
    except Exception:
        current_app.logger.exception('Errore marking next delivery')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/plan', methods=['DELETE'])
def delete_plan():
    """Delete the active terapia plan and its deliveries."""
    try:
        plan = TerapiaPlan.query.first()
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


@sanita_bp.route('/api/plan/extend', methods=['POST'])
def extend_plan():
    """Extend the existing plan by adding the same number of deliveries.
    Can only be called when all current deliveries are marked as received.
    """
    try:
        plan = TerapiaPlan.query.first()
        if not plan:
            return jsonify({'error': 'no_plan', 'message': 'Nessun piano esistente da estendere.'}), 404
        
        # Get all current deliveries
        deliveries = TerapiaDelivery.query.filter_by(plan_id=plan.id).order_by(TerapiaDelivery.delivery_number).all()
        
        if not deliveries:
            return jsonify({'error': 'no_deliveries', 'message': 'Nessuna consegna da estendere.'}), 400
        
        # Check if all deliveries are received
        all_received = all(d.received for d in deliveries)
        if not all_received:
            return jsonify({'error': 'not_all_received', 'message': 'Tutte le consegne devono essere ricevute prima di estendere.'}), 400
        
        # Get the last delivery number
        last_delivery_num = max(d.delivery_number for d in deliveries)
        
        # Count how many deliveries to add (same as current count)
        num_to_add = len(deliveries)
        
        # Add new deliveries
        qty_per_delivery = 2
        for i in range(num_to_add):
            new_delivery_num = last_delivery_num + i + 1
            d = TerapiaDelivery(
                plan_id=plan.id,
                delivery_number=new_delivery_num,
                quantity=qty_per_delivery,
                received=False
            )
            db.session.add(d)
        
        # Update plan totals
        plan.num_deliveries = last_delivery_num + num_to_add
        plan.total_drugs = plan.num_deliveries * qty_per_delivery
        db.session.add(plan)
        
        db.session.commit()
        return jsonify({'plan': plan.to_dict()})
    except Exception:
        current_app.logger.exception('Errore extending plan')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500

