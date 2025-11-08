from app import db
from datetime import datetime


class PasswdCredential(db.Model):
    __tablename__ = 'credentials'

    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String, nullable=False)
    servizio = db.Column(db.String, nullable=False)
    utenza = db.Column(db.String, nullable=True)
    password = db.Column(db.Text, nullable=True)  # encrypted
    altro = db.Column(db.Text, nullable=True)     # encrypted

    def to_decrypted_dict(self, decrypt_fn):
        return {
            'id': self.id,
            'CATEGORIA': self.categoria,
            'SERVIZIO': self.servizio,
            'UTENZA': self.utenza,
            'PASSWORD': decrypt_fn(self.password) if self.password else '',
            'ALTRO': decrypt_fn(self.altro) if self.altro else ''
        }
