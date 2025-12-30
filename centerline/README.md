# Centerline - Barn Management Billing System

A simple, efficient web application for managing lesson charges, lease payments, board payments, and client balances at a dressage barn.

## Features

- **Dashboard**: Quick overview of all clients and their current balances
- **Client Management**: Add, edit, and track clients with horse assignments
- **Transaction Tracking**: Log lessons, charges, and payments with full history
- **Services Management**: Configure lesson types, lease rates, and board prices
- **Mobile-Friendly**: Responsive design works great on phones at the barn
- **Fast Data Entry**: Minimal clicks to log lessons and payments

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

   This will create the database with sample services:
   - Private Lesson - $75
   - Semi-Private Lesson - $50
   - Half Lease - $400/month
   - Full Board - $800/month

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Open in your browser:**
   ```
   http://localhost:5000
   ```

## Usage Guide

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
│   ├── dashboard.html
│   ├── clients.html
│   ├── client_detail.html
│   ├── client_form.html
│   ├── services.html
│   └── service_form.html
└── static/               # Static files (currently unused)
    ├── css/
    └── js/
```

## Database Schema

### Clients
- id (primary key)
- name
- email
- phone
- horse_assignment
- active (boolean)
- created_date

### Services
- id (primary key)
- service_name
- price
- billing_frequency (one-time or monthly)
- active (boolean)

### Transactions
- id (primary key)
- client_id (foreign key)
- service_id (foreign key, optional)
- amount
- transaction_date
- transaction_type (charge or payment)
- notes

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
