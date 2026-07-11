from datetime import datetime, timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from datetime import datetime
from pymongo import MongoClient
from influxdb_client import InfluxDBClient

app = FastAPI(
    title="CocoaSecure IoT API",
    description="API de supervision IoT pour le séchage du cacao et la détection de fraude",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# MongoDB
MONGO_URL = "mongodb://mongodb:27017"
MONGO_DB = "cocoasecure"

mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[MONGO_DB]

# InfluxDB
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "cacao-token-123456"
INFLUX_ORG = "CocoaSecure"
INFLUX_BUCKET = "cacao_measurements"

influx_client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

@app.get("/")
def root():
    return {
        "message": "Bienvenue sur CocoaSecure IoT API",
        "status": "running"
    }

@app.get("/health")
def health():
    return {
        "status": "OK",
        "service": "api",
        "mongodb": True,
        "influxdb": True,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/alerts")
def get_alerts():
    alerts = list(
        mongo_db["fraud_alerts"]
        .find({}, {"_id": 0})
        .sort("createdAt", -1)
        .limit(50)
    )

    return {
        "count": len(alerts),
        "alerts": alerts
    }

@app.get("/readings/latest")
def get_latest_readings():
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "sensor_measurements")
      |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity" or r["_field"] == "co2" or r["_field"] == "light" or r["_field"] == "battery" or r["_field"] == "signal" or r["_field"] == "fraudScore")
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
                "lotId": record.values.get("lotId")
            })

    return {
        "count": len(results),
        "readings": results
    }


@app.get("/readings/history")
def get_readings_history():
    """
    Retourne :
    - readings : mesures individuelles utilisées par les graphiques ;
    - injections : paquets de mesures regroupés par capteur et horodatage.
    """

    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) =>
          r["_measurement"] == "sensor_measurements"
      )
      |> filter(fn: (r) =>
          r["_field"] == "temperature" or
          r["_field"] == "humidity" or
          r["_field"] == "co2" or
          r["_field"] == "battery" or
          r["_field"] == "signal" or
          r["_field"] == "light" or
          r["_field"] == "fraudScore"
      )
      |> sort(columns: ["_time"], desc: false)
      |> limit(n: 500)
    '''

    tables = influx_client.query_api().query(query)

    readings = []

    # Regroupement des champs appartenant à une même injection.
    grouped_injections = {}

    for table in tables:
        for record in table.records:
            record_time = str(record.get_time())
            device_id = record.values.get("deviceId")
            site = record.values.get("site")
            lot_id = record.values.get("lotId")
            field = record.get_field()
            value = record.get_value()

            reading = {
                "time": record_time,
                "field": field,
                "value": value,
                "deviceId": device_id,
                "site": site,
                "lotId": lot_id
            }

            readings.append(reading)

            # Une injection est identifiée par le capteur et l'horodatage.
            injection_key = f"{device_id}|{record_time}"

            if injection_key not in grouped_injections:
                grouped_injections[injection_key] = {
                    "time": record_time,
                    "deviceId": device_id,
                    "site": site,
                    "lotId": lot_id,
                    "values": {}
                }

            grouped_injections[injection_key]["values"][field] = value

    # Historique des injections, de la plus récente à la plus ancienne.
    injections = sorted(
        grouped_injections.values(),
        key=lambda injection: injection["time"],
        reverse=True
    )

    return {
        "count": len(readings),
        "injectionCount": len(injections),
        "readings": readings,
        "injections": injections[:10]
    }

@app.get("/dashboard")
def get_dashboard():
    """
    Retourne les indicateurs principaux du dashboard CocoaSecure.

    Une injection correspond à un ensemble complet de mesures
    enregistrées pour un capteur à un instant donné.
    """

    try:
        # Date correspondant aux dernières 24 heures.
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        since_24h_iso = since_24h.isoformat()

        # ---------------------------------------------------------
        # 1. Alertes critiques enregistrées pendant les dernières 24 h
        # ---------------------------------------------------------
        critical_alerts_24h = mongo_db["fraud_alerts"].count_documents({
            "niveau": "CRITICAL",
            "createdAt": {
                "$gte": since_24h_iso
            }
        })

        # ---------------------------------------------------------
        # 2. Dernières alertes MongoDB
        # ---------------------------------------------------------
        latest_alerts = list(
            mongo_db["fraud_alerts"]
            .find({}, {"_id": 0})
            .sort("createdAt", -1)
            .limit(5)
        )

        # ---------------------------------------------------------
        # 3. Récupération des injections InfluxDB des dernières 24 h
        #
        # pivot transforme les 7 champs d'une même injection
        # en une seule ligne :
        #
        # temperature, humidity, co2, light,
        # battery, signal et fraudScore
        # ---------------------------------------------------------
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) =>
              r["_measurement"] == "sensor_measurements"
          )
          |> pivot(
              rowKey: ["_time"],
              columnKey: ["_field"],
              valueColumn: "_value"
          )
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
                    "lotId": values.get("lotId")
                })

        # ---------------------------------------------------------
        # 4. Élimination d'éventuels doublons
        #
        # Une injection est identifiée par :
        # deviceId + timestamp
        # ---------------------------------------------------------
        unique_injections = {}

        for injection in injections:
            key = (
                injection.get("deviceId"),
                injection.get("time")
            )

            unique_injections[key] = injection

        injection_list = list(unique_injections.values())

        # Nombre réel d'injections et non nombre de champs InfluxDB.
        injections_24h = len(injection_list)

        # Capteurs distincts ayant envoyé une mesure dans les 24 heures.
        active_sensors = len({
            injection["deviceId"]
            for injection in injection_list
            if injection.get("deviceId")
        })

        # Sites distincts supervisés pendant les dernières 24 heures.
        supervised_sites = len({
            injection["site"]
            for injection in injection_list
            if injection.get("site")
        })

        return {
            "summary": {
                "injections24h": injections_24h,
                "criticalAlerts24h": critical_alerts_24h,
                "activeSensors": active_sensors,
                "supervisedSites": supervised_sites
            },
            "latestAlerts": latest_alerts
        }

    except Exception as error:
        print(f"Erreur dashboard : {error}")

        return {
            "summary": {
                "injections24h": 0,
                "criticalAlerts24h": 0,
                "activeSensors": 0,
                "supervisedSites": 0
            },
            "latestAlerts": [],
            "error": str(error)
        }

    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "sensor_measurements")
      |> limit(n: 100)
    '''

    tables = influx_client.query_api().query(query)

    total_readings = 0
    fields = {}

    for table in tables:
        for record in table.records:
            total_readings += 1
            field = record.get_field()
            fields[field] = fields.get(field, 0) + 1

    return {
        "status": "OK",
        "generatedAt": datetime.utcnow().isoformat(),
        "summary": {
            "totalAlerts": total_alerts,
            "criticalAlerts": critical_alerts,
            "totalReadings": total_readings,
            "fieldsDetected": fields
        },
        "latestAlerts": latest_alerts
    }