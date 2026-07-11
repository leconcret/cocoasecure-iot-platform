# Architecture du projet Cacao Secure IoT

## 1. Contexte

Le projet Cacao Secure IoT vise à superviser en temps réel le séchage du cacao dans la région de San-Pédro.  
Les données issues des capteurs IoT permettent de contrôler les conditions de séchage et de détecter les tentatives de fraude sur les mesures.

## 2. Sites simulés

| Site | Localisation | Capteurs |
|---|---|---|
| Site A | San-Pédro Nord | ESP01, ESP02 |
| Site B | Grand-Béréby | ESP03, ESP04 |
| Site C | Tabou | ESP05 |

## 3. Données collectées

Chaque capteur envoie :

- deviceId
- site
- lot
- température
- humidité
- CO2
- luminosité
- position GPS
- timestamp

## 4. Pipeline IoT

ESP32 / Wokwi → MQTT → Node-RED → InfluxDB + MongoDB → Redis Sentinel → FastAPI → React → Grafana / Prometheus / Kibana

## 5. Rôle des composants

| Composant | Rôle |
|---|---|
| ESP32 / Wokwi | Simulation des capteurs |
| MQTT | Transport des messages IoT |
| Node-RED | Filtrage, enrichissement, détection d’anomalies |
| InfluxDB | Stockage des mesures temporelles |
| MongoDB | Stockage des métadonnées des capteurs et sites |
| Redis Sentinel | Cache, Pub/Sub, haute disponibilité |
| FastAPI | API REST, Swagger, JWT, WebSocket |
| React | Dashboard utilisateur/admin |
| Grafana | Visualisation des métriques |
| Prometheus | Collecte des métriques |
| Kibana | Analyse des logs |
| Nginx | Load balancer devant les API |
| Docker Compose | Déploiement de la stack complète |

## 6. Scénario de fraude

Un attaquant injecte de faux messages MQTT pour modifier les mesures d’humidité d’un lot de cacao.  
L’objectif est de faire croire qu’un lot est conforme alors que son taux d’humidité réel est trop élevé.

Le système détecte cette fraude par :

- incohérence brutale des valeurs ;
- dépassement des seuils métier ;
- répétition suspecte de messages ;
- identité capteur non reconnue ;
- horodatage anormal.

## 7. Profils utilisateurs

| Profil | Rôle |
|---|---|
| Utilisateur | Consulter les mesures, historiques et alertes |
| Administrateur | Gérer les capteurs, seuils, sites, utilisateurs et services |

## 8. Objectif final

Produire une plateforme IoT distribuée, sécurisée, observable et déployable avec Docker Compose.