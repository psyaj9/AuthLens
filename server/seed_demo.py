from db.seed_demo import DEMO_PASSWORD, DEMO_USERS, seed_demo_data
from db.session import init_db


def main() -> None:
    init_db()
    seed_demo_data()
    emails = ", ".join(email for email, _name, _role in DEMO_USERS)
    print(f"Seeded demo users ({emails}) with password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
