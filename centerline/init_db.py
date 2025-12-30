"""
Initialize database with sample data
"""
from models import Database, Service

def init_database():
    """Initialize database and add sample services"""
    db = Database()
    db.init_db()
    print("Database schema created successfully!")

    # Create service instances
    service_model = Service(db)

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

    print("\nDatabase initialized with sample services!")
    print("You can now run the application with: python app.py")


if __name__ == "__main__":
    init_database()
