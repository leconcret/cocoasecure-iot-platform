# Cacao Secure IoT

Monitoring temps réel du séchage du cacao à San-Pédro avec détection de fraude sur les données capteurs IoT.

## Objectif

Ce projet vise à superviser les conditions de séchage du cacao à partir de capteurs IoT simulés, détecter les anomalies et tentatives de fraude, puis afficher les résultats dans un dashboard web.

## Architecture globale

ESP32 / Wokwi → MQTT → Node-RED → InfluxDB + MongoDB → Redis Sentinel → FastAPI → React → Grafana / Prometheus / Kibana