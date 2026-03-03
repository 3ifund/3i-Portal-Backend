"""
Update the testuser MongoDB document to map to CAPS (Capstone Holding Corp, company_id=3).

Usage:
    python scripts/update_testuser.py
"""

from pymongo import MongoClient

MONGO_URI = "mongodb://10.90.98.123:27017/?replicaSet=rs0"
DB_NAME = "three_i_fund_portal"


def update():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    result = db["users"].update_one(
        {"user_id": "testuser"},
        {"$set": {
            "company_id": "3",
            "company_name": "Capstone Holding Corp",
        }},
    )

    if result.matched_count:
        print("Updated testuser -> company_id='3', company_name='Capstone Holding Corp'")
    else:
        print("testuser not found in MongoDB. Run seed_db.py first.")

    # Verify
    user = db["users"].find_one({"user_id": "testuser"})
    if user:
        print(f"  user_id:      {user['user_id']}")
        print(f"  company_id:   {user['company_id']}")
        print(f"  company_name: {user['company_name']}")

    client.close()


if __name__ == "__main__":
    update()
