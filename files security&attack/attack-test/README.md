# Dossier `attack/` — CocoaSecure IoT Platform

Scripts d'attaque pour la partie sécurité (rôle RIST) du mini-projet.
Ciblent l'infrastructure réelle du projet : broker `cacao_mosquitto`,
topic `cacao/sanpedro/measurements`, sans authentification (`allow_anonymous true`).

## Installation

```bash
cd attack/
python3 -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

Assure-toi que la stack tourne (`docker-compose up`) et que le port 1883
est bien accessible depuis ta machine (déjà exposé dans le docker-compose du projet).

## Ordre d'exécution recommandé pour la démo / le rapport L2

### 1. A1 — Sniffing
Voir `A1_sniffing_guide.md`. Capture Wireshark/tshark du trafic en clair.
**À faire en premier et à garder en arrière-plan** pendant les scripts A2/A3
pour capturer leur trafic aussi.

```bash
sudo tshark -i any -f "tcp port 1883" -Y "mqtt" -w capture_A1_sniffing.pcap
```

### 2. A2 — Injection / usurpation
```bash
python A2_injection.py --mode extreme --count 5 --interval 2
```
Puis vérifier dans Node-RED (debug "FRAUDES DETECTÉES") et MongoDB (`fraud_alerts`)
que l'injection a bien déclenché une alerte.

Pour tester la limite de la détection par seuils fixes :
```bash
python A2_injection.py --mode plausible --count 5
```

### 3. A3 — Replay
Terminal 1 :
```bash
python A3_replay.py --mode capture
```
Déclenche un envoi normal côté Node-RED (bouton inject), le script capture
automatiquement le premier message "NORMAL" reçu.

Terminal 2 (après capture) :
```bash
python A3_replay.py --mode replay --file captured_message.json --repeat 3
```

## Preuves à collecter pour le rapport L2 (2 pages min., avant 17h J5)

| Preuve | Fichier / capture |
|---|---|
| Trafic MQTT en clair | `capture_A1_sniffing.pcap` + screenshot payload lisible |
| Injection réussie sans authentification | Logs console A2 + debug Node-RED + doc MongoDB `fraud_alerts` |
| Détection de l'injection "extreme" | fraudScore élevé dans MongoDB |
| Non-détection de l'injection "plausible" | Absence d'alerte malgré valeurs limites — à discuter comme limite du système |
| Replay accepté comme mesure valide | Message rejoué visible dans InfluxDB sans alerte de fraude associée |

Ces résultats serviront aussi de baseline "avant sécurisation" pour la
comparaison quantitative demandée en C2 une fois TLS + auth mutuelle en place.
