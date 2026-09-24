"""Load demo claims:  python seed.py          (add demo data)
                      python seed.py --reset  (delete ALL claims first, then add demo data)"""
import sys
from app import create_app, get_db, seed_demo

app = create_app()
with app.app_context():
    db = get_db()
    if "--reset" in sys.argv:
        db.execute("DELETE FROM claims")
        db.commit()
        print("All claims deleted.")
    print(f"Added {seed_demo(db)} demo claims.")
