"""
Initialize database with sample data
"""
from models import Database, Service, User, Client
import hashlib

def hash_password(password: str) -> str:
    """Simple password hashing (use proper hashing in production)"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    """Initialize database and add sample services"""
    db = Database()
    db.init_db()
    print("Database schema created successfully!")

    # Create model instances
    service_model = Service(db)
    user_model = User(db)
    client_model = Client(db)

    # Add sample services
    sample_services = [
        ("Private Lesson", 75.00, "one-time"),
        ("Semi-Private Lesson", 50.00, "one-time"),
        ("Half Lease", 400.00, "monthly"),
        ("Full Board", 800.00, "monthly"),
    ]

    for service_name, price, billing_frequency in sample_services:
        service_model.create(service_name, price, billing_frequency)
        print(f"Created service: {service_name} - ${price}")

    # Create sample clients
    client1_id = client_model.create("Sarah Johnson", "sarah@example.com", "555-1234", "Leasing Boo")
    client2_id = client_model.create("Mike Davis", "mike@example.com", "555-5678", "Rides school horses")
    print(f"\nCreated sample clients: Sarah Johnson, Mike Davis")

    # Create sample users
    # Admin user
    admin_id = user_model.create("admin", hash_password("admin123"), "admin")
    print(f"Created admin user - username: admin, password: admin123")

    # Staff user
    staff_id = user_model.create("staff", hash_password("staff123"), "staff")
    print(f"Created staff user - username: staff, password: staff123")

    # Client users
    user_model.create("sarah", hash_password("sarah123"), "client", client1_id)
    user_model.create("mike", hash_password("mike123"), "client", client2_id)
    print(f"Created client users - sarah/sarah123, mike/mike123")

    print("\n" + "=" * 60)
    print("Database initialized successfully!")
    print("=" * 60)
    print("\nDefault Users Created:")
    print("  Admin:  username: admin  | password: admin123")
    print("  Staff:  username: staff  | password: staff123")
    print("  Client: username: sarah  | password: sarah123")
    print("  Client: username: mike   | password: mike123")
    print("\nYou can now run the application with: python app.py")
    print("=" * 60)


if __name__ == "__main__":
    init_database()
