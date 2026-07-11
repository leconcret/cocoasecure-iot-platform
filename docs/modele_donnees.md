# Modèle de données — CocoaSecure-IoT

## 1. Collections MongoDB

### users
Stocke les comptes utilisateurs.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant MongoDB |
| nom | String | Nom complet |
| email | String | Adresse email |
| passwordHash | String | Mot de passe chiffré |
| role | String | ADMIN ou OPERATEUR |
| createdAt | Date | Date de création |

### sites
Stocke les sites de séchage.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant du site |
| nom | String | Nom du site |
| ville | String | Ville |
| region | String | Région |
| responsable | String | Responsable |
| gps | GeoJSON Point | Coordonnées GPS |

### devices
Stocke les capteurs IoT.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant MongoDB |
| deviceId | String | Identifiant ESP32 |
| nom | String | Nom du capteur |
| siteId | ObjectId | Site associé |
| lotId | ObjectId | Lot associé |
| status | String | ONLINE ou OFFLINE |
| installedAt | Date | Date d’installation |

### lots
Stocke les lots de cacao suivis.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant du lot |
| code | String | Code du lot |
| cooperative | String | Coopérative |
| siteId | ObjectId | Site associé |
| dateDebutSechage | Date | Date de début |
| statut | String | EN_COURS, CONFORME, FRAUDE |

### alerts
Stocke les alertes métier et sécurité.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant alerte |
| type | String | HUMIDITE, TEMPERATURE, FRAUDE, SECURITE |
| niveau | String | INFO, WARNING, CRITICAL |
| message | String | Message d’alerte |
| deviceId | String | Capteur concerné |
| lotId | ObjectId | Lot concerné |
| createdAt | Date | Date création |
| status | String | ACTIVE ou RESOLUE |

### security_incidents
Stocke les événements de sécurité.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant incident |
| typeAttaque | String | SNIFFING, REPLAY, INJECTION, USURPATION |
| source | String | Adresse source ou identité suspecte |
| deviceId | String | Capteur concerné |
| preuve | String | Trace ou payload suspect |
| createdAt | Date | Date incident |

### rules
Stocke les règles de détection.

| Champ | Type | Description |
|---|---|---|
| _id | ObjectId | Identifiant règle |
| nom | String | Nom de la règle |
| type | String | HUMIDITE, TEMPERATURE, CO2, FRAUDE |
| seuilMin | Number | Valeur minimale |
| seuilMax | Number | Valeur maximale |
| active | Boolean | Règle active ou non |

## 2. Mesure InfluxDB

### Measurement : sensor_measurements

Tags :

| Tag | Description |
|---|---|
| deviceId | Identifiant du capteur |
| site | Nom du site |
| lot | Code du lot |

Fields :

| Field | Type | Description |
|---|---|---|
| temperature | Float | Température en °C |
| humidity | Float | Humidité en % |
| co2 | Float | CO2 en ppm |
| light | Float | Luminosité |
| battery | Float | Niveau batterie simulé |
| fraudScore | Float | Score de suspicion |

Timestamp :

| Élément | Description |
|---|---|
| time | Date et heure de la mesure |

## 3. Clés Redis

| Clé | Usage |
|---|---|
| last_measure:{deviceId} | Dernière mesure d’un capteur |
| device_status:{deviceId} | État ONLINE/OFFLINE |
| alerts:active | Liste des alertes actives |
| rate_limit:{userId} | Limitation de requêtes API |
| session:{userId} | Session utilisateur |

## 4. Canaux Redis Pub/Sub

| Canal | Usage |
|---|---|
| measurements | Diffusion temps réel des mesures |
| alerts | Diffusion temps réel des alertes |
| security | Diffusion des incidents de sécurité |