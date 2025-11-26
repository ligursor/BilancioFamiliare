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
            # By default, when creating a new plan we should NOT mark deliveries or doses as administered.
            d = TerapiaDelivery(
                plan_id=plan.id,
                delivery_number=delivery_num,
                quantity=qty_per_delivery,
                received=False,
                dose1=False,
                dose2=False
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
        # Toggle received state; do NOT auto-mark doses as administered here.
        new_state = not bool(delivery.received)
        delivery.received = new_state
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
        # Mark delivery as received (arrival). Do NOT auto-mark doses as administered;
        # individual doses (dose1/dose2) are recorded when the user confirms a date.
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


@sanita_bp.route('/api/delivery/<int:did>/schedule', methods=['POST'])
def schedule_delivery(did):
    """Set or update the scheduled delivery date for a specific delivery."""
    try:
        delivery = TerapiaDelivery.query.get(did)
        if not delivery:
            return jsonify({'error': 'not_found'}), 404
        
        data = request.get_json() or {}
        date_str = data.get('date')
        if not date_str:
            return jsonify({'error': 'missing_date'}), 400
        
        # Parse the date
        parts = date_str.split('-')
        scheduled_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        
        delivery.scheduled_delivery_date = scheduled_date
        db.session.add(delivery)
        db.session.commit()
        
        # Return the full plan to update UI
        plan = TerapiaPlan.query.get(delivery.plan_id)
        return jsonify({'plan': plan.to_dict() if plan else None})
    except Exception:
        current_app.logger.exception('Errore scheduling delivery')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500


@sanita_bp.route('/api/delivery/<int:did>/confirm-delivery', methods=['POST'])
def confirm_delivery(did):
    """Confirm that scheduled delivery has arrived."""
    try:
        delivery = TerapiaDelivery.query.get(did)
        if not delivery:
            return jsonify({'error': 'not_found'}), 404
        
        # Mark delivery as confirmed
        delivery.delivery_confirmed = True
        delivery.received = True  # Mark as received
        db.session.add(delivery)
        db.session.commit()
        
        # Return the full plan to update UI
        plan = TerapiaPlan.query.get(delivery.plan_id)
        return jsonify({'plan': plan.to_dict() if plan else None})
    except Exception:
        current_app.logger.exception('Errore confirming delivery')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500





@sanita_bp.route('/api/delivery/mark_date', methods=['POST'])
def mark_delivery_by_date():
    """Mark the delivery that covers the given scheduled date as received.
    Expected JSON: { date: 'YYYY-MM-DD' }
    The server computes the schedule (every 14 days from plan.start_date) and
    finds which delivery covers that schedule index (each delivery has quantity doses).
    Then the delivery.received flag is set to True and the updated plan returned.
    """
    data = request.get_json() or {}
    dt = data.get('date')
    try:
        if not dt:
            return jsonify({'error': 'invalid'}), 400
        plan = TerapiaPlan.query.first()
        if not plan:
            return jsonify({'error': 'no_plan'}), 404

        # parse date
        parts = dt.split('-')
        if len(parts) != 3:
            return jsonify({'error': 'invalid_date'}), 400
        target = date(int(parts[0]), int(parts[1]), int(parts[2]))

        # build schedules every 14 days from plan.start_date until plan end (dec 31 next year)
        start = plan.start_date
        end_year = start.year + 1
        last_day = date(end_year, 12, 31)
        schedules = []
        cur = start
        while cur <= last_day:
            schedules.append(cur)
            cur = cur + timedelta(days=14)

        # find index of target date in schedules
        try:
            idx = next(i for i, s in enumerate(schedules) if s == target)
        except StopIteration:
            current_app.logger.info('mark_delivery_by_date: date_not_scheduled target=%s start=%s', target, start)
            return jsonify({'error': 'date_not_scheduled', 'message': 'La data non corrisponde a una somministrazione programmata.'}), 400

        # iterate deliveries in ascending delivery_number and find which covers idx
        deliveries = TerapiaDelivery.query.filter_by(plan_id=plan.id).order_by(TerapiaDelivery.delivery_number).all()
        covered_count = 0
        found = None
        for d in deliveries:
            qty = int(d.quantity or 0)
            range_start = covered_count
            range_end = covered_count + qty - 1
            if range_start <= idx <= range_end:
                found = d
                break
            covered_count += qty

        if not found:
            current_app.logger.info('mark_delivery_by_date: no_matching_delivery idx=%s schedules_len=%s deliveries=%s', idx, len(schedules), len(deliveries))
            return jsonify({'error': 'no_matching_delivery', 'message': 'Nessuna consegna corrisponde alla data selezionata.'}), 400

        # determine which dose within the delivery corresponds to idx
        dose_index = idx - covered_count  # 0-based
        if dose_index < 0 or dose_index >= int(found.quantity or 0):
            current_app.logger.info('mark_delivery_by_date: invalid_dose_index dose_index=%s qty=%s', dose_index, found.quantity)
            return jsonify({'error': 'invalid_dose_index', 'message': 'Indice dose non valido.'}), 400

        # Enforce global ordering across received deliveries:
        # only the earliest (in delivery_number order) dose that belongs to a received delivery
        # and that is not yet administered can be marked. Compute its schedule index.
        try:
            global_idx = 0
            earliest_pending_idx = None
            for d_iter in deliveries:
                q = int(d_iter.quantity or 0)
                for j in range(q):
                    # consider only doses from deliveries that have been received
                    if d_iter.received:
                        is_administered = True
                        if j == 0:
                            is_administered = bool(d_iter.dose1)
                        else:
                            is_administered = bool(d_iter.dose2)
                        if not is_administered:
                            earliest_pending_idx = global_idx
                            break
                    global_idx += 1
                if earliest_pending_idx is not None:
                    break
        except Exception:
            earliest_pending_idx = None

        # If there is an earlier pending dose (in a received delivery) and the user
        # is trying to mark a different later scheduled date, reject and suggest the required date.
        if earliest_pending_idx is not None and idx != earliest_pending_idx:
            try:
                required_iso = schedules[earliest_pending_idx].isoformat()
            except Exception:
                required_iso = None
            current_app.logger.info('mark_delivery_by_date: global_order_violation target_idx=%s required_idx=%s', idx, earliest_pending_idx)
            return jsonify({'error': 'order_violation', 'message': 'Devi marcare prima le somministrazioni in ordine cronologico: marcare prima le dosi non registrate della consegna più vecchia.', 'required_date': required_iso}), 400

        # Check whether the corresponding dose is already recorded
        already = False
        if dose_index == 0:
            already = bool(found.dose1)
        else:
            already = bool(found.dose2)

        if already:
            return jsonify({'error': 'already_received', 'message': 'Questa dose è già stata marcata come somministrata.'}), 400

        # Ensure the delivery has been received (covered) before allowing marking a dose
        if not found.received:
            current_app.logger.info('mark_delivery_by_date: delivery_not_received delivery_id=%s', getattr(found, 'id', None))
            return jsonify({'error': 'not_covered', 'message': 'La consegna non è stata ricevuta. Aggiungi la consegna prima di marcare la somministrazione.'}), 400

        # Enforce dose ordering: cannot mark dose2 before dose1
        if dose_index == 1 and not bool(found.dose1):
            current_app.logger.info('mark_delivery_by_date: order_violation delivery_id=%s', getattr(found, 'id', None))
            # compute the scheduled date that corresponds to dose1 for this delivery
            try:
                # covered_count is the index of the first dose of this delivery in the schedules list
                required_date = schedules[covered_count]
                required_iso = required_date.isoformat()
            except Exception:
                required_iso = None
            return jsonify({'error': 'order_violation', 'message': 'Devi marcare prima la prima dose (dose1) prima di marcare la seconda.', 'required_date': required_iso}), 400

        # Mark the specific dose as administered
        if dose_index == 0:
            found.dose1 = True
        else:
            found.dose2 = True

        # If all doses are administered, set delivery.received true as well
        if (int(found.quantity or 0) <= 1 and found.dose1) or (int(found.quantity or 0) >= 2 and found.dose1 and found.dose2):
            found.received = True

        db.session.add(found)
        db.session.commit()

        plan = TerapiaPlan.query.get(plan.id)
        return jsonify({'plan': plan.to_dict()})
    except Exception:
        current_app.logger.exception('Errore marking delivery by date')
        db.session.rollback()
        return jsonify({'error': 'internal'}), 500

