from app import db


class PasswdSecurityConfig(db.Model):
    __tablename__ = 'security_config'

    id = db.Column(db.Integer, primary_key=True)
    salt = db.Column(db.LargeBinary, nullable=True)
    test_encrypted = db.Column(db.Text, nullable=True)
