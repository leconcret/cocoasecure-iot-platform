# Guide — Sécurisation TLS 1.3 + X.509 (CocoaSecure IoT Platform)

Ce guide active la version sécurisée du broker en parallèle de la version
vulnérable, pour permettre la comparaison "avant / après" exigée par le sujet
(section 7 — Haute disponibilité et sécurité).

---

## Étape 1 — Générer les certificats

```bash
cd security/certs
chmod +x generate_certs.sh
./generate_certs.sh
```

Génère `ca.crt/key`, `server.crt/key`, et 4 certificats clients (`esp01` à `esp04`).

---

## Étape 2 — Créer le fichier de mots de passe (listener WebSocket)

```bash
docker run --rm -v $(pwd)/security/broker:/mosquitto/config \
    eclipse-mosquitto:2 mosquitto_passwd -c -b /mosquitto/config/passwd admin_dashboard MotDePasseFort123!
```

---

## Étape 3 — Ajouter le service sécurisé dans `docker-compose.yml`

Ajouter (sans supprimer le service `mosquitto` vulnérable existant, pour
pouvoir démontrer les deux configurations côte à côte pendant la soutenance) :

```yaml
  mosquitto-secure:
    image: eclipse-mosquitto:2
    container_name: cacao_mosquitto_secure
    ports:
      - "8883:8883"
      - "9002:9002"
    volumes:
      - ./security/broker/mosquitto_secure.conf:/mosquitto/config/mosquitto.conf
      - ./security/certs:/mosquitto/certs:ro
      - ./security/broker/passwd:/mosquitto/config/passwd:ro
    restart: unless-stopped
```

> Pour la démonstration finale en soutenance (J10), il est recommandé de
> **désactiver** le service `mosquitto` vulnérable (`allow_anonymous true`)
> et de ne garder que `mosquitto-secure`, afin de montrer une architecture
> réellement durcie. Le gardera actif seulement pour rejouer les captures
> "avant" si besoin de démo comparative live.

---

## Étape 4 — Reconfigurer Node-RED pour utiliser TLS

Dans le noeud `mqtt-broker` (Node-RED) :
- Server : `mosquitto-secure`
- Port : `8883`
- Onglet **Security** :
  - Enable secure (SSL/TLS) : coché
  - Verify server certificate : coché
  - Certificate : `esp01.crt` (ou un certificat dédié Node-RED, ex: `nodered.crt`,
    à générer avec le même script en ajoutant `nodered` à la liste des devices)
  - Private key : `esp01.key`
  - CA certificate : `ca.crt`
- Onglet **Connection** : `Protocol` = MQTT v3.1.1, `TLS version` = 1.3 si l'option existe.

---

## Étape 5 — Vérifier la connexion sécurisée en ligne de commande

```bash
# Publication autorisée (avec certificat client valide)
mosquitto_pub -h localhost -p 8883 \
    --cafile security/certs/ca.crt \
    --cert security/certs/esp01.crt \
    --key security/certs/esp01.key \
    --tls-version tlsv1.3 \
    -t cacao/sanpedro/measurements \
    -m '{"deviceId":"ESP01","test":"connexion securisee"}'

# Doit afficher une erreur de handshake TLS (aucun certificat fourni)
mosquitto_pub -h localhost -p 8883 \
    -t cacao/sanpedro/measurements \
    -m '{"test":"sans certificat"}'
```

---

## Étape 6 — Rejouer les attaques A1/A2/A3 sur le broker sécurisé (validation)

C'est l'étape qui produit les preuves "après sécurisation" attendues en C2.

### A1 — Sniffing (doit échouer à révéler le contenu)
```bash
sudo tshark -i any -f "tcp port 8883" -Y "tls" -w capture_A1_apres_TLS.pcap
```
Résultat attendu : les paquets apparaissent comme `Application Data` chiffrée,
aucun payload JSON lisible — à comparer au screenshot "avant" de `A1_sniffing_guide.md`.

### A2 — Injection (doit échouer, refus de connexion)
Modifier temporairement `A2_injection.py` : changer `BROKER_PORT = 8883` et
**ne pas** fournir de certificat client (l'attaquant n'a pas accès à `esp01.key`).
Résultat attendu : `client.connect()` échoue avec une erreur TLS handshake
(`[SSL: CERTIFICATE_VERIFY_FAILED]` ou refus de connexion côté broker).

### A3 — Replay (doit échouer sans certificat valide, ou nécessiter le vol du certificat)
Même principe : sans le fichier `esp01.key` (censé rester uniquement sur
l'ESP32 physique/simulé), le rejeu est impossible. Cela illustre une limite
importante à mentionner dans le rapport : **le mTLS empêche l'usurpation
réseau, mais pas le vol physique d'un certificat déjà déployé sur un
capteur compromis** — d'où l'intérêt de compléter par un anti-replay
applicatif (nonce/TTL) si le temps le permet.

---

## Tableau de synthèse pour le rapport final (comparaison quantitative)

| Attaque | Avant sécurisation | Après TLS 1.3 + mTLS |
|---|---|---|
| A1 — Sniffing | Payload JSON lisible en clair | Application Data chiffrée, illisible |
| A2 — Injection | Acceptée sans authentification | Rejetée — pas de certificat client |
| A3 — Replay | Acceptée comme mesure valide | Impossible sans certificat client volé |
| Connexions anonymes | Illimitées | Bloquées (`allow_anonymous false`) |
