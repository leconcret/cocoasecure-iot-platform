# A1 — Sniffing MQTT (CocoaSecure IoT Platform)

## Cible
- Broker : `cacao_mosquitto` (eclipse-mosquitto:2)
- Port : 1883 (MQTT clair, sans TLS)
- Topic observé : `cacao/sanpedro/measurements`
- Config vulnérable confirmée : `allow_anonymous true` dans `broker/mosquitto.conf`

## Objectif
Prouver que le trafic MQTT circule en clair et que n'importe qui sur le réseau peut lire
les mesures des capteurs (température, humidité, CO2, deviceId, lotId...) sans authentification.

---

## Méthode 1 — Wireshark (interface graphique)

1. Ouvrir Wireshark, sélectionner l'interface réseau utilisée par Docker
   (sur la plupart des setups : `docker0`, `br-xxxxx`, ou l'interface locale si le broker
   est exposé sur `localhost:1883`).

2. Appliquer le filtre d'affichage :
   ```
   mqtt
   ```

3. Lancer une capture, puis déclencher une publication (bouton "inject" dans Node-RED
   ou attendre le prochain envoi automatique).

4. Dans la liste des paquets, repérer les paquets `MQTT Publish Message`.
   Clic droit → **Follow → TCP Stream** pour voir le payload JSON complet en clair.

5. Capturer une preuve : screenshot du payload lisible + `File → Export Specified Packets`
   pour sauvegarder le `.pcap`.

**Preuve attendue dans le rapport L2 :** capture `.pcap` + screenshot montrant un JSON du type
`{"deviceId":"ESP01","site":"San-Pedro Nord","temperature":37.2,...}` lisible sans déchiffrement.

---

## Méthode 2 — tshark (ligne de commande, plus rapide pour la démo)

```bash
# Capture en direct, filtrée sur le port MQTT
sudo tshark -i any -f "tcp port 1883" -Y "mqtt" -V

# Capture vers un fichier .pcap pour preuve
sudo tshark -i any -f "tcp port 1883" -w capture_A1_sniffing.pcap

# Extraction rapide des payloads MQTT Publish déjà capturés
tshark -r capture_A1_sniffing.pcap -Y "mqtt.msgtype == 3" -T fields -e mqtt.topic -e mqtt.msg
```

Si Wireshark/tshark tourne sur ta machine hôte et que Mosquitto est dans Docker,
assure-toi que le port `1883` est bien publié dans `docker-compose.yml` (c'est déjà le cas :
`ports: - "1883:1883"`), donc la capture sur `lo`/`localhost` suffit.

---

## Ce que ça prouve pour le rapport (STRIDE — Information Disclosure)

| Élément | Constat |
|---|---|
| Chiffrement transport | Aucun — payload JSON lisible en clair |
| Authentification broker | Aucune — `allow_anonymous true` |
| Données exposées | deviceId, site, lotId, mesures, timestamp |
| Impact | Un attaquant passif sur le réseau lit toutes les mesures de toutes les coopératives |

Cette capture sert de baseline "avant sécurisation". Il faudra refaire exactement la même
capture après activation de TLS 1.3 pour montrer que le payload devient illisible
(Application Data chiffrée au lieu de MQTT Publish en clair).
