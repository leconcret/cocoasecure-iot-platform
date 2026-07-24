#!/bin/bash
# ─────────────────────────────────────────────────────────────
# generate_certs.sh — CocoaSecure IoT Platform
# Génère une CA locale + certificat serveur (broker) + certificats
# clients (un par ESP32) pour l'authentification mutuelle TLS (mTLS).
#
# Usage :
#   chmod +x generate_certs.sh
#   ./generate_certs.sh
#
# Résultat dans ./certs/ :
#   ca.crt, ca.key                    -> Autorité de certification locale
#   server.crt, server.key            -> Certificat du broker Mosquitto
#   esp01.crt, esp01.key (x4)         -> Certificats clients par capteur
# ─────────────────────────────────────────────────────────────

set -e

OUT_DIR="./certs"
DAYS_CA=3650
DAYS_CERT=825
COUNTRY="CI"
STATE="Bas-Sagnoa"
CITY="San-Pedro"
ORG="CocoaSecure-IoT"

mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

echo "=== 1. Génération de l'autorité de certification (CA) ==="
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days $DAYS_CA \
    -out ca.crt \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=CocoaSecure-CA"

echo ""
echo "=== 2. Génération du certificat serveur (broker Mosquitto) ==="
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=mosquitto"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days $DAYS_CERT -sha256
rm server.csr

echo ""
echo "=== 3. Génération des certificats clients (un par ESP32) ==="
for DEVICE in esp01 esp02 esp03 esp04; do
    openssl genrsa -out "${DEVICE}.key" 2048
    openssl req -new -key "${DEVICE}.key" -out "${DEVICE}.csr" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=${DEVICE}"
    openssl x509 -req -in "${DEVICE}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
        -out "${DEVICE}.crt" -days $DAYS_CERT -sha256
    rm "${DEVICE}.csr"
    echo "  -> ${DEVICE}.crt / ${DEVICE}.key générés"
done

echo ""
echo "=== 4. Permissions ==="
chmod 644 *.crt
chmod 600 *.key ca.key

echo ""
echo "=== Terminé ==="
echo "Fichiers générés dans $(pwd) :"
ls -la *.crt *.key

echo ""
echo "IMPORTANT : ca.key doit rester strictement privé (ne pas commit sur Git)."
echo "Ajouter au .gitignore : security/certs/*.key"
