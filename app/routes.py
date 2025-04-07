from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from .models import User, InvestmentInput, FundAllocation
from datetime import datetime

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password.')
            return redirect(url_for('main.login'))

        login_user(user)
        return redirect(url_for('main.dashboard'))

    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if current_user.is_admin():
        pending = InvestmentInput.query.filter_by(status='Pending').all()
        history = InvestmentInput.query.filter_by(status='Approved').all()
        users = User.query.filter_by(role='investor').all()
        total_contributions = sum(user.total_approved_investments() for user in users)

        ownership_data = [{
            'username': user.username,
            'percentage': round((user.total_approved_investments() / total_contributions) * 100, 2)
            if total_contributions > 0 else 0
        } for user in users]

        fund_allocations = FundAllocation.query.all()

        return render_template(
            'admin_history.html',
            pending=pending,
            history=history,
            ownership_data=ownership_data,
            investors=users,
            fund_allocations=fund_allocations,
            total_contributions=total_contributions
        )

    # Investor view
    approved_investments = [i for i in current_user.investments if i.status == 'Approved']

    users = User.query.filter_by(role='investor').all()
    total_contributions = sum(user.total_approved_investments() for user in users)

    ownership_data = [{
        'username': user.username,
        'percentage': round((user.total_approved_investments() / total_contributions) * 100, 2)
        if total_contributions > 0 else 0
    } for user in users]

    fund_allocations_raw = FundAllocation.query.all()
    fund_allocations = [{
        'name': f.name,
        'percentage': round((f.amount / total_contributions) * 100, 2)
        if total_contributions > 0 else 0
    } for f in fund_allocations_raw]

    return render_template(
        'dashboard.html',
        investments=approved_investments,
        ownership_data=ownership_data,
        fund_allocations=fund_allocations
    )

@main.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_investment():
    if current_user.is_admin():
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
        except (ValueError, TypeError):
            flash("Please enter a valid amount.")
            return redirect(url_for('main.submit_investment'))

        comment = request.form.get('comment', '')
        date_input = request.form.get('date_submitted')

        if date_input:
            try:
                date_submitted = datetime.strptime(date_input, '%Y-%m-%d')
            except ValueError:
                flash('Invalid date format. Please use the date picker.')
                return redirect(url_for('main.submit_investment'))
        else:
            date_submitted = datetime.utcnow()

        new_input = InvestmentInput(
            amount=amount,
            comment=comment.strip(),
            status='Pending',
            user_id=current_user.id,
            date_submitted=date_submitted
        )

        db.session.add(new_input)
        db.session.commit()
        flash('✅ Investment submitted and pending approval!')
        return redirect(url_for('main.dashboard'))

    return render_template('investor_form.html')

@main.route('/approve/<int:investment_id>')
@login_required
def approve(investment_id):
    if not current_user.is_admin():
        return redirect(url_for('main.dashboard'))
    investment = InvestmentInput.query.get_or_404(investment_id)
    investment.status = 'Approved'
    investment.date_approved = datetime.utcnow()
    db.session.commit()
    flash('Investment approved!')
    return redirect(url_for('main.dashboard'))

@main.route('/reject/<int:investment_id>')
@login_required
def reject(investment_id):
    if not current_user.is_admin():
        return redirect(url_for('main.dashboard'))
    investment = InvestmentInput.query.get_or_404(investment_id)
    investment.status = 'Rejected'
    db.session.commit()
    flash('Investment rejected!')
    return redirect(url_for('main.dashboard'))

@main.route('/create-user', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_admin():
        flash('Access denied.')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists.')
            return redirect(url_for('main.create_user'))

        new_user = User(username=username, password=generate_password_hash(password), role='investor')
        db.session.add(new_user)
        db.session.commit()
        flash('Investor account created successfully.')
        return redirect(url_for('main.dashboard'))

    return render_template('create_user.html')

@main.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin():
        flash('Access denied.')
        return redirect(url_for('main.dashboard'))

    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot delete admin accounts.')
        return redirect(url_for('main.dashboard'))

    for investment in user.investments:
        db.session.delete(investment)

    db.session.delete(user)
    db.session.commit()
    flash(f'Investor "{user.username}" has been deleted.')
    return redirect(url_for('main.dashboard'))

@main.route('/create-allocation', methods=['POST'])
@login_required
def create_allocation():
    if not current_user.is_admin():
        flash('Access denied.')
        return redirect(url_for('main.dashboard'))

    name = request.form['name']
    amount = float(request.form['amount'])

    new_allocation = FundAllocation(name=name, amount=amount)
    db.session.add(new_allocation)
    db.session.commit()
    flash(f'${amount} allocated to "{name}"')
    return redirect(url_for('main.dashboard'))

@main.route('/history', methods=['GET'])
@login_required
def investment_history():
    if not current_user.is_admin():
        flash('Access denied.')
        return redirect(url_for('main.dashboard'))

    selected_user_id = request.args.get('user_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    users = User.query.filter_by(role='investor').all()

    query = InvestmentInput.query.filter_by(status='Approved')

    if selected_user_id and selected_user_id != "all":
        query = query.filter_by(user_id=int(selected_user_id))
    if start_date:
        query = query.filter(InvestmentInput.date_approved >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(InvestmentInput.date_approved <= datetime.strptime(end_date, '%Y-%m-%d'))

    approved = query.order_by(InvestmentInput.date_approved.desc()).all()

    return render_template(
        'investment_history.html',
        users=users,
        approved=approved,
        selected_user_id=selected_user_id,
        start_date=start_date,
        end_date=end_date
    )
