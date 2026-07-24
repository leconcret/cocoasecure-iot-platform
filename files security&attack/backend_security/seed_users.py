"""
seed_users.py — CocoaSecure IoT API
Crée les comptes utilisateurs initiaux dans MongoDB (collection "users"),
avec mots de passe hashés bcrypt.

Usage :
    python seed_users.py

À exécuter une seule fois (ou après un `docker-compose down -v` qui vide
le volume mongo_data). Idempotent : ne recrée pas un compte déjà existant.
"""

from pymongo import MongoClient
from auth import hash_password, Role

MONGO_URL = "mongodb://localhost:27017"  # depuis l'hôte ; utiliser "mongodb://mongodb:27017" si exécuté dans un conteneur
MONGO_DB = "cocoasecure"

DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "AdminCacao2026!",   # à changer immédiatement en production
        "role": Role.ADMIN.value,
        "site": None,
    },
    {
        "username": "operateur.sanpedro",
        "password": "OperateurSP2026!",
        "role": Role.OPERATOR.value,
        "site": "San-Pedro Nord",
    },
    {
        "username": "viewer.demo",
        "password": "ViewerDemo2026!",
        "role": Role.VIEWER.value,
        "site": None,
    },
]


def main():
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    users = db["users"]

    users.create_index("username", unique=True)

    for u in DEFAULT_USERS:
        if users.find_one({"username": u["username"]}):
            print(f"[seed] '{u['username']}' existe déjà — ignoré.")
            continue

        users.insert_one({
            "username": u["username"],
            "hashedPassword": hash_password(u["password"]),
            "role": u["role"],
            "site": u["site"],
        })
        print(f"[seed] Utilisateur créé : {u['username']} (rôle={u['role']})")

    print("\n[seed] Terminé. Identifiants de démonstration :")
    for u in DEFAULT_USERS:
        print(f"  - {u['username']} / {u['password']}  (rôle={u['role']})")
    print("\n[seed] IMPORTANT : ces mots de passe sont pour la démo uniquement. "
          "Ne jamais les utiliser en production.")


if __name__ == "__main__":
    main()
