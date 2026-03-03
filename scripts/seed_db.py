"""
Seed the three_i_fund_portal MongoDB database.
Creates collections (users, eloc_state, eloc_data) and inserts a test user.

Usage:
    python scripts/seed_db.py
"""

from pymongo import MongoClient
import bcrypt

MONGO_URI = "mongodb://10.90.98.123:27017/?replicaSet=rs0"
DB_NAME = "three_i_fund_portal"


def seed():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # Create collections with indexes
    # -- users --
    if "users" not in db.list_collection_names():
        db.create_collection("users")
    db["users"].create_index("user_id", unique=True)

    # -- eloc_state --
    if "eloc_state" not in db.list_collection_names():
        db.create_collection("eloc_state")
    db["eloc_state"].create_index("eloc_id", unique=True)
    db["eloc_state"].create_index("company_id")

    # -- eloc_data --
    if "eloc_data" not in db.list_collection_names():
        db.create_collection("eloc_data")
    db["eloc_data"].create_index([("eloc_id", 1), ("step", 1)])
    db["eloc_data"].create_index("company_id")

    # Insert test users (skip if they already exist)
    test_users = [
        {
            "user_id": "admin",
            "password_hash": bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
            "role": "admin",
            "company_id": "3i_fund",
            "company_name": "3i Fund",
        },
        {
            "user_id": "testuser",
            "password_hash": bcrypt.hashpw("test123".encode(), bcrypt.gensalt()).decode(),
            "role": "user",
            "company_id": "3",
            "company_name": "Capstone Holding Corp",
        },
    ]

    for user in test_users:
        existing = db["users"].find_one({"user_id": user["user_id"]})
        if existing:
            print(f"  User '{user['user_id']}' already exists, skipping.")
        else:
            db["users"].insert_one(user)
            print(f"  Created user '{user['user_id']}' ({user['role']})")

    print("\nDone. Database and collections ready.")
    print(f"  DB: {DB_NAME}")
    print(f"  Collections: users, eloc_state, eloc_data")
    print(f"\nTest logins:")
    print(f"  Admin:  user_id=admin     password=admin123")
    print(f"  User:   user_id=testuser  password=test123")

    client.close()


if __name__ == "__main__":
    seed()
