from app import db
from datetime import date


class TerapiaPlan(db.Model):
    __tablename__ = 'terapia_plan'
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    total_drugs = db.Column(db.Integer, nullable=False, default=0)
    num_deliveries = db.Column(db.Integer, nullable=False, default=0)

    deliveries = db.relationship('TerapiaDelivery', backref='plan', cascade='all, delete-orphan', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'total_drugs': self.total_drugs,
            'num_deliveries': self.num_deliveries,
            'deliveries': [d.to_dict() for d in self.deliveries.order_by(TerapiaDelivery.delivery_number).all()]
        }


class TerapiaDelivery(db.Model):
    __tablename__ = 'terapia_delivery'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('terapia_plan.id'), nullable=False)
    delivery_number = db.Column(db.Integer, nullable=False)  # Progressive number within the plan
    quantity = db.Column(db.Integer, nullable=False, default=2)
    received = db.Column(db.Boolean, nullable=False, default=False)
    # Track individual doses inside a delivery (typically 2 doses)
    dose1 = db.Column(db.Boolean, nullable=False, default=False)
    dose2 = db.Column(db.Boolean, nullable=False, default=False)
    # Delivery scheduling: scheduled date and confirmation flag
    scheduled_delivery_date = db.Column(db.Date, nullable=True)  # Data programmata consegna
    delivery_confirmed = db.Column(db.Boolean, nullable=False, default=False)  # Consegna confermata

    def to_dict(self):
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'delivery_number': self.delivery_number,
            'quantity': self.quantity,
            'received': bool(self.received),
            'dose1': bool(self.dose1),
            'dose2': bool(self.dose2),
            'scheduled_delivery_date': self.scheduled_delivery_date.isoformat() if self.scheduled_delivery_date else None,
            'delivery_confirmed': bool(self.delivery_confirmed)
        }
