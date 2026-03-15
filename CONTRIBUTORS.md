# Java-Microservice-Template

This is a production-ready Spring Boot microservice template. It follows a **feature-based structure** and includes modules for core configuration, security, shared utilities, tasks, and feature-specific logic.

```
service-name/
├── src/
│   ├── main/
│   │   ├── java/com/iothub/service/
│   │   │
│   │   │   ├── core/       # Global configuration (WebConfig, OpenApiConfig, SecurityConfig)
│   │   │   │
│   │   │   ├── template/                 # Feature domain (similar to apps/orders)
│   │   │   │   ├── controller/          # REST controllers (API layer)
│   │   │   │   │
│   │   │   │   ├── service/             # Business logic (Use Cases)
│   │   │   │   │
│   │   │   │   ├── entity/              # JPA Entities (Database schema)
│   │   │   │   │
│   │   │   │   ├── repository/          # Data access layer (Spring Data Repositories)
│   │   │   │   │
│   │   │   │   └── dto/                 # Request/Response DTOs (API models)
│   │   │   │
│   │   │   ├── common/                   # Shared utilities, exceptions, mappers, middleware
│   │   │   │
│   │   │   ├── tasks/                    # Scheduled jobs, async tasks
│   │   │
│   │   └── resources/               # Application configs, DB migrations (Flyway/Liquibase)
│   │
│   └── test/
│       └── java/com/iothub/service/
│           ├── template/                 # Unit and integration tests for feature modules
│           │
│           ├── core/                     # Tests for core configuration and security
│           │
│           └── common/                   # Tests for shared utilities
│
├── docker/                             # Dockerfiles and Docker Compose configs
│ 
├── scripts/                            # CI/CD and deployment scripts
│ 
├── docker-compose.yml                  # Docker Compose entrypoint
│ 
├── .env.example                       # Example environment variables
│ 
├── pom.xml                            # Build and dependency management
│ 
└── README.md                          # Project overview and instructions

```

## Project Structure

- `core/` – global configurations and Spring Boot bootstrap
- `core/security/` – Spring Security setup (JWT, authentication, authorization)
- `common/` – shared utilities, mappers, exceptions
- `template/` – feature module (example)
  - `controller/` – REST endpoints
  - `service/` – business logic
  - `repository/` – data access layer (Spring Data JPA)
  - `entity/` – JPA entities
  - `dto/` – request/response objects
- `tasks/` – scheduled jobs, async messaging
- `resources/` – configuration files and database migrations
- `test/` – unit and integration tests organized by feature

## Testing

- **Unit tests**: test single classes in isolation (service layer, utility classes)
- **Integration tests**: test multiple layers together (controller → service → repository)
- **Application context test**: ensures Spring Boot context loads properly (`ServiceApplicationIT.java`)

## Best Practices

- Keep DTOs in the feature module (`dto/`) instead of entity
- Controller should be thin, delegating to service layer
- Feature-based structure scales well as the project grows
- Security configuration is centralized in `core/security/`
- Use Flyway or Liquibase for database migrations
