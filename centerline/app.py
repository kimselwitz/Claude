"""
Centerline - Barn Management Billing System
Main Flask Application
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from models import Database, Client, Service, Transaction, User, Message, ChatGroup
from datetime import datetime
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'centerline-barn-management-secret-key-change-in-production'

# Initialize database
db = Database()
client_model = Client(db)
service_model = Service(db)
transaction_model = Transaction(db)
user_model = User(db)
message_model = Message(db)
group_model = ChatGroup(db)


def hash_password(password: str) -> str:
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        if not user_model.is_admin(session['user_id']):
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = user_model.get_by_username(username)
        if user and user['password_hash'] == hash_password(password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            user_model.update_last_seen(user['id'])
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


@app.route('/')
@login_required
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

    # Get unread message count
    unread_count = message_model.get_unread_count(session['user_id'])

    return render_template('dashboard.html', clients=client_balances, unread_count=unread_count)


@app.route('/clients')
@login_required
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


# ============================================================================
# MESSAGING ROUTES
# ============================================================================

@app.route('/messages')
@login_required
def messages_inbox():
    """Messages inbox - shows conversations and broadcasts"""
    conversations = message_model.get_user_conversations(session['user_id'])
    broadcasts = message_model.get_broadcasts(limit=10)
    groups = group_model.get_user_groups(session['user_id'])
    unread_count = message_model.get_unread_count(session['user_id'])

    return render_template('messages_inbox.html',
                         conversations=conversations,
                         broadcasts=broadcasts,
                         groups=groups,
                         unread_count=unread_count)


@app.route('/messages/conversation/<int:other_user_id>')
@login_required
def conversation(other_user_id):
    """View conversation with specific user"""
    other_user = user_model.get_by_id(other_user_id)
    if not other_user:
        flash('User not found', 'error')
        return redirect(url_for('messages_inbox'))

    messages = message_model.get_direct_messages(session['user_id'], other_user_id)

    # Mark messages as read
    message_model.mark_conversation_as_read(session['user_id'], other_user_id)

    # Get all users for new message dropdown
    all_users = user_model.get_all()

    return render_template('conversation.html',
                         other_user=other_user,
                         messages=messages,
                         all_users=all_users)


@app.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Send a direct message"""
    recipient_id = request.form.get('recipient_id', type=int)
    message_text = request.form.get('message_text', '').strip()

    if not recipient_id or not message_text:
        flash('Recipient and message text are required', 'error')
        return redirect(request.referrer or url_for('messages_inbox'))

    message_model.create(
        sender_id=session['user_id'],
        recipient_id=recipient_id,
        message_text=message_text
    )

    flash('Message sent!', 'success')
    return redirect(url_for('conversation', other_user_id=recipient_id))


@app.route('/messages/broadcast', methods=['GET', 'POST'])
@admin_required
def broadcast_message():
    """Send broadcast message (admin only)"""
    if request.method == 'POST':
        message_text = request.form.get('message_text', '').strip()

        if not message_text:
            flash('Message text is required', 'error')
            return render_template('broadcast.html')

        message_model.create(
            sender_id=session['user_id'],
            message_text=message_text,
            is_broadcast=True
        )

        flash('Broadcast sent to all users!', 'success')
        return redirect(url_for('messages_inbox'))

    return render_template('broadcast.html')


@app.route('/groups')
@login_required
def groups():
    """List all chat groups"""
    user_groups = group_model.get_user_groups(session['user_id'])
    all_groups = group_model.get_all() if session['role'] == 'admin' else []

    return render_template('groups.html', user_groups=user_groups, all_groups=all_groups)


@app.route('/group/<int:group_id>')
@login_required
def group_chat(group_id):
    """View group chat"""
    group = group_model.get_by_id(group_id)
    if not group:
        flash('Group not found', 'error')
        return redirect(url_for('groups'))

    # Check if user is member
    members = group_model.get_members(group_id)
    is_member = any(m['id'] == session['user_id'] for m in members)

    if not is_member and session['role'] != 'admin':
        flash('You are not a member of this group', 'error')
        return redirect(url_for('groups'))

    messages = message_model.get_group_messages(group_id)

    return render_template('group_chat.html',
                         group=group,
                         messages=messages,
                         members=members,
                         is_member=is_member)


@app.route('/group/create', methods=['GET', 'POST'])
@login_required
def create_group():
    """Create new chat group"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Group name is required', 'error')
            all_users = user_model.get_all()
            return render_template('group_form.html', all_users=all_users)

        group_id = group_model.create(name, session['user_id'], description)

        # Add selected members
        member_ids = request.form.getlist('members')
        for member_id in member_ids:
            if int(member_id) != session['user_id']:  # Creator already added
                group_model.add_member(group_id, int(member_id))

        flash(f'Group "{name}" created successfully!', 'success')
        return redirect(url_for('group_chat', group_id=group_id))

    all_users = user_model.get_all()
    return render_template('group_form.html', all_users=all_users)


@app.route('/group/<int:group_id>/send', methods=['POST'])
@login_required
def send_group_message(group_id):
    """Send message to group"""
    message_text = request.form.get('message_text', '').strip()

    if not message_text:
        flash('Message text is required', 'error')
        return redirect(url_for('group_chat', group_id=group_id))

    # Check if user is member
    members = group_model.get_members(group_id)
    is_member = any(m['id'] == session['user_id'] for m in members)

    if not is_member and session['role'] != 'admin':
        flash('You are not a member of this group', 'error')
        return redirect(url_for('groups'))

    message_model.create(
        sender_id=session['user_id'],
        group_id=group_id,
        message_text=message_text
    )

    return redirect(url_for('group_chat', group_id=group_id))


@app.route('/group/<int:group_id>/add_member', methods=['POST'])
@login_required
def add_group_member(group_id):
    """Add member to group (admin or group admin only)"""
    user_id = request.form.get('user_id', type=int)

    if not user_id:
        flash('User is required', 'error')
        return redirect(url_for('group_chat', group_id=group_id))

    # Check permissions
    members = group_model.get_members(group_id)
    is_group_admin = any(m['id'] == session['user_id'] and m['is_admin'] for m in members)

    if not is_group_admin and session['role'] != 'admin':
        flash('Only group admins can add members', 'error')
        return redirect(url_for('group_chat', group_id=group_id))

    group_model.add_member(group_id, user_id)
    flash('Member added successfully!', 'success')
    return redirect(url_for('group_chat', group_id=group_id))


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
