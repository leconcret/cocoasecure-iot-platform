"""
main.py — CocoaSecure IoT API (version sécurisée)

Changements par rapport à la version originale :
- Ajout de l'authentification JWT (/auth/login, /auth/me)
- Protection RBAC des routes existantes (viewer / operator / admin)
- CORS restreint (plus de allow_origins=["*"])
- Rate limiting basique sur /auth/login (anti brute-force, via slowapi)

Toute la logique métier (requêtes InfluxDB/MongoDB) est INCHANGÉE par rapport
à l'original — seules les couches d'authentification et de sécurité sont ajoutées.
"""

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pymongo import MongoClient
from influxdb_client import InfluxDBClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from auth import (
    Role, Token, TokenData, UserOut,
    authenticate_user, create_access_token, get_current_user,
    require_viewer, require_operator, require_admin,
)

# ─────────────────────────────────────────────────────────────
# Rate limiting (contre-mesure STRIDE — Denial of Service, C5)
# ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="CocoaSecure IoT API",
    description="API de supervision IoT pour le séchage du cacao et la détection de fraude",
    version="1.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─────────────────────────────────────────────────────────────
# CORS restreint — remplace allow_origins=["*"] de la version d'origine
# ─────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:5173",   # frontend React (Vite dev server)
    "http://localhost:3000",   # au cas où le frontend tourne sur un autre port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─────────────────────────────────────────────────────────────
# MongoDB (inchangé)
# ─────────────────────────────────────────────────────────────
MONGO_URL = "mongodb://mongodb:27017"
MONGO_DB = "cocoasecure"

mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[MONGO_DB]

# ─────────────────────────────────────────────────────────────
# InfluxDB (inchangé)
# ─────────────────────────────────────────────────────────────
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "cacao-token-123456"
INFLUX_ORG = "CocoaSecure"
INFLUX_BUCKET = "cacao_measurements"

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


# ─────────────────────────────────────────────────────────────
# Routes d'authentification
# ─────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=Token)
@limiter.limit("5/minute")  # anti brute-force : 5 tentatives / minute / IP
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(mongo_db["users"], form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = Role(user["role"])
    access_token = create_access_token(username=user["username"], role=role)

    return Token(access_token=access_token, role=role)


@app.get("/auth/me", response_model=UserOut)
def read_current_user(current_user: TokenData = Depends(get_current_user)):
    user_doc = mongo_db["users"].find_one({"username": current_user.username}, {"_id": 0})
    return UserOut(
        username=current_user.username,
        role=current_user.role,
        site=user_doc.get("site") if user_doc else None,
    )


# ─────────────────────────────────────────────────────────────
# Routes publiques (aucune donnée sensible)
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Bienvenue sur CocoaSecure IoT API", "status": "running"}


@app.get("/health")
def health():
    return {
        "status": "OK",
        "service": "api",
        "mongodb": True,
        "influxdb": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# Routes protégées — niveau VIEWER minimum (lecture des dashboards)
# ─────────────────────────────────────────────────────────────
@app.get("/dashboard")
def get_dashboard(current_user: TokenData = Depends(require_viewer)):
    try:
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        since_24h_iso = since_24h.isoformat()

        critical_alerts_24h = mongo_db["fraud_alerts"].count_documents({
            "niveau": "CRITICAL",
            "createdAt": {"$gte": since_24h_iso}
        })

        latest_alerts = list(
            mongo_db["fraud_alerts"].find({}, {"_id": 0}).sort("createdAt", -1).limit(5)
        )

        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r["_measurement"] == "sensor_measurements")
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
        '''
        tables = influx_client.query_api().query(query)

        injections = []
        for table in tables:
            for record in table.records:
                values = record.values
                injections.append({
                    "time": str(record.get_time()),
                    "deviceId": values.get("deviceId"),
                    "site": values.get("site"),
                    "lotId": values.get("lotId"),
                })

        unique_injections = {
            (i.get("deviceId"), i.get("time")): i for i in injections
        }
        injection_list = list(unique_injections.values())

        injections_24h = len(injection_list)
        active_sensors = len({i["deviceId"] for i in injection_list if i.get("deviceId")})
        supervised_sites = len({i["site"] for i in injection_list if i.get("site")})

        return {
            "summary": {
                "injections24h": injections_24h,
                "criticalAlerts24h": critical_alerts_24h,
                "activeSensors": active_sensors,
                "supervisedSites": supervised_sites,
            },
            "latestAlerts": latest_alerts,
        }

    except Exception as error:
        print(f"Erreur dashboard : {error}")
        return {
            "summary": {
                "injections24h": 0,
                "criticalAlerts24h": 0,
                "activeSensors": 0,
                "supervisedSites": 0,
            },
            "latestAlerts": [],
            "error": str(error),
        }


@app.get("/readings/latest")
def get_latest_readings(current_user: TokenData = Depends(require_viewer)):
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "sensor_measurements")
      |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity" or
                            r["_field"] == "co2" or r["_field"] == "light" or
                            r["_field"] == "battery" or r["_field"] == "signal" or
                            r["_field"] == "fraudScore")
      |> group(columns: ["deviceId", "_field"])
      |> last()
      |> group()
      |> sort(columns: ["_time"], desc: true)
    '''
    tables = influx_client.query_api().query(query)

    results = []
    for table in tables:
        for record in table.records:
            results.append({
                "time": str(record.get_time()),
                "measurement": record.get_measurement(),
                "field": record.get_field(),
                "value": record.get_value(),
                "deviceId": record.values.get("deviceId"),
                "site": record.values.get("site"),
                "lotId": record.values.get("lotId"),
            })

    return {"count": len(results), "readings": results}


@app.get("/readings/history")
def get_readings_history(current_user: TokenData = Depends(require_viewer)):
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "sensor_measurements")
      |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity" or
                            r["_field"] == "co2" or r["_field"] == "battery" or
                            r["_field"] == "signal" or r["_field"] == "light" or
                            r["_field"] == "fraudScore")
      |> sort(columns: ["_time"], desc: false)
      |> limit(n: 500)
    '''
    tables = influx_client.query_api().query(query)

    readings = []
    grouped_injections = {}

    for table in tables:
        for record in table.records:
            record_time = str(record.get_time())
            device_id = record.values.get("deviceId")
            site = record.values.get("site")
            lot_id = record.values.get("lotId")
            field = record.get_field()
            value = record.get_value()

            readings.append({
                "time": record_time, "field": field, "value": value,
                "deviceId": device_id, "site": site, "lotId": lot_id,
            })

            key = f"{device_id}|{record_time}"
            if key not in grouped_injections:
                grouped_injections[key] = {
                    "time": record_time, "deviceId": device_id,
                    "site": site, "lotId": lot_id, "values": {},
                }
            grouped_injections[key]["values"][field] = value

    injections = sorted(grouped_injections.values(), key=lambda i: i["time"], reverse=True)

    return {
        "count": len(readings),
        "injectionCount": len(injections),
        "readings": readings,
        "injections": injections[:10],
    }


# ─────────────────────────────────────────────────────────────
# Routes protégées — niveau OPERATOR minimum (données de fraude détaillées)
# ─────────────────────────────────────────────────────────────
@app.get("/alerts")
def get_alerts(current_user: TokenData = Depends(require_operator)):
    alerts = list(
        mongo_db["fraud_alerts"].find({}, {"_id": 0}).sort("createdAt", -1).limit(50)
    )
    return {"count": len(alerts), "alerts": alerts}


# ─────────────────────────────────────────────────────────────
# Routes protégées — niveau ADMIN minimum (gestion utilisateurs)
# ─────────────────────────────────────────────────────────────
@app.get("/admin/users")
def list_users(current_user: TokenData = Depends(require_admin)):
    users = list(mongo_db["users"].find({}, {"_id": 0, "hashedPassword": 0}))
    return {"count": len(users), "users": users}
