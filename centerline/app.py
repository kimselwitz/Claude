"""
Centerline - Barn Management Billing System
Main Flask Application
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import Database, Client, Service, Transaction
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'centerline-barn-management-secret-key-change-in-production'

# Initialize database
db = Database()
client_model = Client(db)
service_model = Service(db)
transaction_model = Transaction(db)


@app.route('/')
def dashboard():
    """Dashboard showing all clients with balances"""
    clients = client_model.get_all()

    # Calculate balances for each client
    client_balances = []
    for client in clients:
        balance = client_model.get_balance(client['id'])
        client_balances.append({
            'id': client['id'],
            'name': client['name'],
            'horse_assignment': client['horse_assignment'],
            'balance': balance
        })

    # Sort by balance (highest debt first)
    client_balances.sort(key=lambda x: x['balance'], reverse=True)

    return render_template('dashboard.html', clients=client_balances)


@app.route('/clients')
def clients():
    """List all clients"""
    all_clients = client_model.get_all(active_only=False)
    return render_template('clients.html', clients=all_clients)


@app.route('/client/<int:client_id>')
def client_detail(client_id):
    """Client detail page with transaction history"""
    client = client_model.get_by_id(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('clients'))

    transactions = transaction_model.get_all(client_id=client_id)
    balance = client_model.get_balance(client_id)
    services = service_model.get_all()

    return render_template('client_detail.html',
                         client=client,
                         transactions=transactions,
                         balance=balance,
                         services=services)


@app.route('/client/add', methods=['GET', 'POST'])
def add_client():
    """Add new client"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        horse_assignment = request.form.get('horse_assignment', '')

        if not name:
            flash('Client name is required', 'error')
            return render_template('client_form.html')

        client_id = client_model.create(name, email, phone, horse_assignment)
        flash(f'Client {name} added successfully!', 'success')
        return redirect(url_for('client_detail', client_id=client_id))

    return render_template('client_form.html')


@app.route('/client/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    """Edit client"""
    client = client_model.get_by_id(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('clients'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        horse_assignment = request.form.get('horse_assignment', '')
        active = request.form.get('active') == 'on'

        if not name:
            flash('Client name is required', 'error')
            return render_template('client_form.html', client=client)

        client_model.update(client_id, name, email, phone, horse_assignment, active)
        flash(f'Client {name} updated successfully!', 'success')
        return redirect(url_for('client_detail', client_id=client_id))

    return render_template('client_form.html', client=client)


@app.route('/transaction/add', methods=['POST'])
def add_transaction():
    """Add new transaction (charge or payment)"""
    client_id = request.form.get('client_id', type=int)
    service_id = request.form.get('service_id', type=int)
    amount = request.form.get('amount', type=float)
    transaction_type = request.form.get('transaction_type')
    notes = request.form.get('notes', '')

    if not client_id or not amount or not transaction_type:
        flash('Missing required fields', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    if transaction_type not in ['charge', 'payment']:
        flash('Invalid transaction type', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    # For payments, service_id is optional
    if service_id == 0:
        service_id = None

    transaction_model.create(client_id, amount, transaction_type, service_id, notes)

    client = client_model.get_by_id(client_id)
    type_text = 'charge' if transaction_type == 'charge' else 'payment'
    flash(f'{type_text.capitalize()} of ${amount:.2f} added for {client["name"]}', 'success')

    return redirect(url_for('client_detail', client_id=client_id))


@app.route('/services')
def services():
    """List all services"""
    all_services = service_model.get_all(active_only=False)
    return render_template('services.html', services=all_services)


@app.route('/service/add', methods=['GET', 'POST'])
def add_service():
    """Add new service"""
    if request.method == 'POST':
        service_name = request.form.get('service_name')
        price = request.form.get('price', type=float)
        billing_frequency = request.form.get('billing_frequency')

        if not service_name or not price or not billing_frequency:
            flash('All fields are required', 'error')
            return render_template('service_form.html')

        service_model.create(service_name, price, billing_frequency)
        flash(f'Service {service_name} added successfully!', 'success')
        return redirect(url_for('services'))

    return render_template('service_form.html')


@app.route('/service/<int:service_id>/edit', methods=['GET', 'POST'])
def edit_service(service_id):
    """Edit service"""
    service = service_model.get_by_id(service_id)
    if not service:
        flash('Service not found', 'error')
        return redirect(url_for('services'))

    if request.method == 'POST':
        service_name = request.form.get('service_name')
        price = request.form.get('price', type=float)
        billing_frequency = request.form.get('billing_frequency')
        active = request.form.get('active') == 'on'

        if not service_name or not price or not billing_frequency:
            flash('All fields are required', 'error')
            return render_template('service_form.html', service=service)

        service_model.update(service_id, service_name, price, billing_frequency, active)
        flash(f'Service {service_name} updated successfully!', 'success')
        return redirect(url_for('services'))

    return render_template('service_form.html', service=service)


@app.template_filter('currency')
def currency_filter(value):
    """Format currency"""
    return f"${value:,.2f}"


@app.template_filter('datetime')
def datetime_filter(value):
    """Format datetime"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except:
            return value
    return value.strftime('%m/%d/%Y %I:%M %p')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
