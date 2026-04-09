# IoT Hub Rule Engine Service

Rule evaluation service for processing telemetry events and detecting matched business conditions.

---

## Purpose

The Rule Engine Service owns rule definitions and evaluates incoming telemetry against configured business rules.
It operates as an independent service, enabling scalable and decoupled rule processing.

---

## Responsibilities

* manage rule definitions
* associate rules with devices, metrics, or scopes
* consume validated telemetry events
* select relevant rules for each telemetry event
* evaluate rule conditions
* publish rule match events

---

## Owned Data

* rules
* rule configurations
* rule-to-scope bindings
* rule evaluation metadata

---

## Integrations

### Inbound

* validated telemetry topic (Kafka)
* management clients for rule CRUD (REST API)

### Outbound

* rule match events (Kafka)
* audit-worthy rule lifecycle events

---

## Technology

* Python (**Django**, Django ORM)
* Kafka (e.g. `aiokafka` або `confluent-kafka`)
* ASGI (e.g. `uvicorn` / `daphne`) for concurrent processing
* PostgreSQL
* Docker

---

## Notes

* The service exposes a REST API for rule management.
* Telemetry processing is handled asynchronously via Kafka consumers.
* Healthcheck endpoint is available at `/health/`.
* Designed for horizontal scaling and independent deployment.
