# IoT Hub Rule Engine Service

Rule evaluation service for processing telemetry events and detecting matched business conditions.

## Purpose

The Rule Engine Service owns rule definitions and evaluates incoming telemetry against configured business rules.

## Responsibilities

- manage rule definitions
- associate rules with devices, metrics, or scopes
- consume validated telemetry
- select relevant rules for each telemetry event
- evaluate rule conditions
- publish rule match events

## Owned data

- rules
- rule configuration
- rule-to-scope bindings
- rule evaluation metadata

## Integrations

### Inbound
- validated telemetry topic
- management clients for rule CRUD

### Outbound
- rule match events
- audit-worthy rule lifecycle events

## Technology

- Java
- Kafka
- Docker
