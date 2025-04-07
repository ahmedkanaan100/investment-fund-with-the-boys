from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from . import db, login_manager

# Used by Flask-Login to load users
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --------------------------
# USER MODEL (Admin/Investor)
# --------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'admin' or 'investor'

    # Relationship: One user can have many investment inputs
    investments = db.relationship('InvestmentInput', backref='investor', lazy=True)

    def is_admin(self):
        return self.role == 'admin'

    def total_approved_investments(self):
        return sum(i.amount for i in self.investments if i.status == 'Approved')


# --------------------------
# INVESTMENT INPUT MODEL
# --------------------------
class InvestmentInput(db.Model):
    __tablename__ = 'investments'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    date_approved = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='Pending')  # Pending, Approved, Rejected
    comment = db.Column(db.String(300), nullable=True)

    # Foreign key to link investment to a user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


# --------------------------
# FUND ALLOCATION MODEL
# --------------------------
class FundAllocation(db.Model):
    __tablename__ = 'fund_allocations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Crypto", "Real Estate"
    amount = db.Column(db.Float, nullable=False)      # Dollar amount allocated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
