"""
Modello per i budget per categoria
"""
from app import db


class Budget(db.Model):
    """Budget associato a una categoria"""
    __tablename__ = 'budget'

    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    importo = db.Column(db.Float, nullable=False, default=0.0)

    categoria = db.relationship('Categoria', backref=db.backref('budget', uselist=False))

    def __repr__(self):
        return f'<Budget categoria_id={self.categoria_id} importo={self.importo}>'
