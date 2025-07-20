# GitHub Copilot Rules for MQTT Thermometer Project

## General Rules

### Instruction Maintenance

- **ALWAYS** update this `.github/copilot-instructions.md` file when receiving new instructions or architectural changes from the user
- Keep all sections current with the latest project decisions and patterns
- Document new patterns, tools, or approaches as they are adopted
- Remove outdated information and update examples to reflect current practices

## Project Overview

This is an IoT temperature monitoring system that:

- Collects temperature data from MQTT topics
- Stores data in SQLite database with proper Decimal handling
- Provides a FastAPI web interface with real-time updates
- Deploys via Docker containers to ARM64 Raspberry Pi devices

## Architecture Decisions

### Deployment Strategy

- **CI**: GitHub-hosted runners build ARM64 Docker images
- **CD**: Two self-hosted Raspberry Pi runners ("raspi-home", "raspi-cottage") deploy containers
- **Configuration**: TOML files mounted as volumes, specific to each location
- **Data Persistence**: SQLite database stored in persistent Docker volume
- **Service Management**: Docker Compose with `restart: unless-stopped` policy
- **Deployment Location**: `/srv/mqtt-thermometer` for standardized service placement

### Technology Stack

- **Backend**: FastAPI with uvicorn
- **Database**: SQLite with custom Decimal type handling
- **Frontend**: htmx + Chart.js (no Node.js/NPM)
- **MQTT**: Paho-MQTT client
- **Configuration**: Pydantic Settings with TOML
- **Package Management**: uv
- **Containerization**: Multi-stage Docker builds for ARM64

### Security & Best Practices

- Context manager pattern for database connections
- Parameterized SQL queries (no string formatting)
- Non-root container user
- Separate SSH keys for upload/deploy operations
- Health checks and proper error handling

## Coding Guidelines

### Database Operations

```python
# ALWAYS use context managers for database connections
with get_database_connection() as connection:
    # database operations

# ALWAYS use parameterized queries
cursor.execute("SELECT * FROM table WHERE id=?", (id,))

# NEVER use string formatting in SQL
cursor.execute(f"SELECT * FROM table WHERE id='{id}'")  # DON'T DO THIS
```

### Configuration Management

```python
# Settings are loaded from TOML files via Pydantic
# Support both file-based and environment variable configuration
# Docker containers use mounted config files at /app/config/mqtt-thermometer.toml
```

### Error Handling

```python
# Database functions should return success indicators
def save_temperature(...) -> bool:
    try:
        # operation
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False
```

### Docker Considerations

- Use multi-stage builds for smaller images
- ARM64 platform targeting for Raspberry Pi
- Volume mounts for configuration and data persistence
- Non-root user for security
- Health checks for monitoring
- Docker Compose for service orchestration with `restart: unless-stopped`
- Standard deployment location: `/srv/mqtt-thermometer`

## File Structure Patterns

### Configuration Files

- `mqtt-thermometer.toml`: Main configuration template
- `config/mqtt-thermometer-home.toml`: Home-specific settings
- `config/mqtt-thermometer-cottage.toml`: Cottage-specific settings

### Deployment Scripts

- `scripts/setup-raspi.sh`: Raspberry Pi setup automation
- `Dockerfile`: Multi-stage ARM64 container build
- `.github/workflows/docker-cicd.yml`: CI/CD pipeline

### Docker Compose Files

- `docker-compose.yml`: Generated per Pi with location-specific configuration
- Deployed to `/srv/mqtt-thermometer/docker-compose.yml` on each Pi
- Includes health checks and restart policies

### Code Organization

- `mqtt_thermometer/database.py`: SQLite operations with Decimal handling
- `mqtt_thermometer/mqtt.py`: MQTT client and message processing
- `mqtt_thermometer/service.py`: FastAPI web interface
- `mqtt_thermometer/settings.py`: Pydantic configuration management

## Development Commands

### Local Development

```bash
uv sync                              # Install dependencies
uv run uvicorn mqtt_thermometer.service:app --reload  # Run server
```

### Docker Operations

```bash
docker build --platform linux/arm64 -t mqtt-thermometer .  # Build for Pi
docker-compose up -d                 # Start services
docker-compose down                  # Stop services
docker-compose logs -f               # View logs
```

### Testing

```bash
uv run pytest                       # Run tests
```

## Deployment Process

1. **CI Stage**: GitHub-hosted runner builds ARM64 Docker image
2. **Image Distribution**: Image saved as tar.gz artifact
3. **CD Stage**: Self-hosted Pi runners download and deploy in parallel
4. **Configuration**: Each Pi uses location-specific TOML config
5. **Service Management**: Docker Compose handles container lifecycle
6. **Health Checks**: Verify deployment success via HTTP endpoints

## Environment Variables (Docker)

- `MQTT_THERMOMETER_CONFIG_PATH`: Path to config file
- `MQTT_THERMOMETER_DB_PATH`: Database file location

## Key Dependencies

- fastapi: Web framework
- paho-mqtt: MQTT client
- pydantic-settings: Configuration management
- uvicorn: ASGI server
- sqlite3: Database (built-in)

## Remember

- This project avoids npm/Node.js complexity
- Uses modern Python patterns (uv, Pydantic, async/await)
- Prioritizes simplicity and reliability for IoT deployment
- Configuration is environment-specific but code is shared
- **Docker Compose over systemd**: Use Docker Compose for container management instead of systemd services
- **Standard service location**: Deploy to `/srv/mqtt-thermometer` following FHS guidelines
- **Health checks included**: All containers should include health monitoring
- **Restart policy**: Always use `restart: unless-stopped` for production containers
