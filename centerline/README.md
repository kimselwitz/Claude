# Centerline - Barn Management Billing System

A simple, efficient web application for managing lesson charges, lease payments, board payments, and client balances at a dressage barn.

## Features

### Billing & Client Management
- **Dashboard**: Quick overview of all clients and their current balances
- **Client Management**: Add, edit, and track clients with horse assignments
- **Transaction Tracking**: Log lessons, charges, and payments with full history
- **Services Management**: Configure lesson types, lease rates, and board prices
- **Mobile-Friendly**: Responsive design works great on phones at the barn
- **Fast Data Entry**: Minimal clicks to log lessons and payments

### Messaging & Communication
- **Direct Messaging**: Send private messages to other users
- **Group Chats**: Create and manage group conversations
- **Admin Broadcasts**: Send important announcements to all users (admin only)
- **Unread Notifications**: Badge notifications for unread messages
- **User Authentication**: Secure login system with role-based access

## Quick Start

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Navigate to the centerline directory:**
   ```bash
   cd centerline
   ```

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the database:**
   ```bash
   python init_db.py
   ```

   This will create the database with sample data:
   
   **Services:**
   - Private Lesson - $75
   - Semi-Private Lesson - $50
   - Half Lease - $400/month
   - Full Board - $800/month
   
   **Users:**
   - Admin: admin / admin123
   - Staff: staff / staff123
   - Clients: sarah / sarah123, mike / mike123
   
   **Sample Clients:**
   - Sarah Johnson (linked to user 'sarah')
   - Mike Davis (linked to user 'mike')

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Open in your browser:**
   ```
   http://localhost:5000
   ```

6. **Login with default credentials:**
   - Admin: `admin` / `admin123`
   - Staff: `staff` / `staff123`
   - Client: `sarah` / `sarah123` or `mike` / `mike123`

## Usage Guide

### Logging In

The application now requires login for all features:
1. Navigate to http://localhost:5000
2. Enter your username and password
3. Click "Login"

**Default Users:**
- **Admin** (admin/admin123): Full access to all features including broadcasts
- **Staff** (staff/staff123): Access to billing and messaging features
- **Clients** (sarah/sarah123, mike/mike123): Linked to client records, can view their own info and use messaging

### Adding Your First Client

1. Click "Add New Client" from the Dashboard
2. Enter client name (required)
3. Optionally add email, phone, and horse assignment
4. Click "Save Client"

### Logging a Lesson

From the client detail page:
1. Select the service (e.g., "Private Lesson")
2. Amount auto-fills based on service price
3. Add optional notes (e.g., date or description)
4. Click "Add Charge"

### Recording a Payment

From the client detail page:
1. Enter the payment amount
2. Add optional notes (e.g., "Check #123", "Venmo")
3. Click "Record Payment"

### Managing Services

1. Go to Services from the navigation
2. Add new service types as needed
3. Edit prices or deactivate services no longer offered
4. Services can be one-time (lessons) or monthly (leases, board)

### Understanding Balances

- **Positive balance** (red): Client owes money
- **Negative balance** (green): Client has a credit
- **Zero balance**: Paid in full

Balances automatically calculate as: Total Charges - Total Payments

### Using Messaging Features

**Sending a Direct Message:**
1. Click "Messages" in the navigation
2. Click "New" button
3. Select recipient and type your message
4. Click "Send"

**Viewing Conversations:**
1. Go to Messages inbox
2. Click on any conversation to view message history
3. Type reply and click "Send"
4. Messages are marked as read automatically

**Creating a Group Chat:**
1. Click "Messages" → "Groups"
2. Click "Create New Group"
3. Enter group name and description
4. Select members to add
5. Click "Create Group"

**Sending Group Messages:**
1. Go to Groups and select a group
2. Type your message in the text box
3. Click "Send"
4. All group members will see the message

**Admin Broadcasts:**
(Admin users only)
1. Click "Broadcast" in the navigation
2. Type your announcement message
3. Click "Send Broadcast"
4. Message appears on all users' message inbox

### User Roles

- **Admin**: Full access - manage clients, services, transactions, send broadcasts
- **Staff**: Can manage billing and use messaging features
- **Client**: Can view their own transaction history and use messaging

## Project Structure

```
centerline/
├── app.py                 # Main Flask application
├── models.py              # Database models and queries
├── init_db.py             # Database initialization script
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── centerline.db         # SQLite database (created after init)
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── clients.html
│   ├── client_detail.html
│   ├── client_form.html
│   ├── services.html
│   ├── service_form.html
│   ├── messages_inbox.html
│   ├── conversation.html
│   ├── broadcast.html
│   ├── groups.html
│   ├── group_chat.html
│   └── group_form.html
└── static/               # Static files (currently unused)
    ├── css/
    └── js/
```

## Database Schema

### Billing Tables

**Clients**
- id (primary key)
- name
- email
- phone
- horse_assignment
- active (boolean)
- created_date

**Services**
- id (primary key)
- service_name
- price
- billing_frequency (one-time or monthly)
- active (boolean)

**Transactions**
- id (primary key)
- client_id (foreign key)
- service_id (foreign key, optional)
- amount
- transaction_date
- transaction_type (charge or payment)
- notes

### Messaging Tables

**Users**
- id (primary key)
- username (unique)
- password_hash
- client_id (foreign key, optional - links to client record)
- role (admin, staff, client)
- created_date
- last_seen

**Messages**
- id (primary key)
- sender_id (foreign key → users)
- recipient_id (foreign key → users, optional for broadcasts/groups)
- group_id (foreign key → chat_groups, optional)
- message_text
- is_broadcast (boolean)
- is_read (boolean)
- sent_date

**Chat Groups**
- id (primary key)
- name
- description
- is_broadcast (boolean)
- created_by (foreign key → users)
- created_date

**Group Members**
- id (primary key)
- group_id (foreign key → chat_groups)
- user_id (foreign key → users)
- joined_date
- is_admin (boolean - group admin, not system admin)

## Tips for Barn Owners

### Best Practices

1. **Regular Updates**: Log lessons and charges weekly to keep balances current
2. **Clear Notes**: Add dates or descriptions to help you remember specific transactions
3. **Service Naming**: Include horse names in services (e.g., "Half Lease - Boo") for clarity
4. **Mobile Use**: Bookmark on your phone's home screen for quick access at the barn

### Common Workflows

**Monthly Billing:**
1. At the start of the month, log monthly charges (leases, board)
2. Use the dashboard to see who owes money
3. Send invoices or reminders based on balances

**Weekly Lessons:**
1. After each lesson, open the client's page
2. Quick log: Select service → Add Charge
3. Balance updates instantly

**Payment Processing:**
1. When receiving payment, open client page
2. Log payment with method in notes (check #, Venmo, etc.)
3. Balance automatically updates

## Troubleshooting

**Can't access the application:**
- Make sure you're running `python app.py` from the centerline directory
- Check that port 5000 isn't already in use
- Try accessing from `http://127.0.0.1:5000` instead

**Database errors:**
- Delete `centerline.db` and run `python init_db.py` again
- This will reset everything to a fresh state

**Missing services in dropdown:**
- Check that services are marked as "Active" in the Services page
- Only active services appear in transaction forms

## Customization

### Changing Default Services

Edit `init_db.py` to add your own default services:
```python
sample_services = [
    ("Your Service Name", 100.00, "one-time"),
    ("Your Monthly Service", 500.00, "monthly"),
]
```

Then reinitialize: `python init_db.py`

### Styling

The application uses Bootstrap 5 for styling. To customize colors or layout, edit the `<style>` section in `templates/base.html`.

## Security Note

This application is designed for local use. If you need to access it from other devices on your network or the internet:

1. Change the secret key in `app.py` to a random string
2. Consider adding authentication
3. Use HTTPS in production
4. Never expose the database file publicly

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the usage guide
- Ensure all dependencies are installed correctly

## License

This project is provided as-is for barn management purposes.
