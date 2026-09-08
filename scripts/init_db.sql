-- =============================================================================
-- Vayu-X — database initialization
-- Runs automatically on first Postgres container start (docker-compose).
-- =============================================================================

-- PostGIS: geometry columns for cyclone positions, tracks, and alert geofences
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- TimescaleDB: observations and forecast points are time-series, and range
-- queries over a multi-season archive must stay fast
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- After Alembic creates the tables, convert the time-series ones to hypertables:
--
--   SELECT create_hypertable('observations', 'observed_at', if_not_exists => TRUE);
--   SELECT create_hypertable('forecast_points', 'valid_at', if_not_exists => TRUE);
--
-- These are commented out because the tables do not exist yet at init time.
-- Run them from `make migrate` or an Alembic post-migration step.
-- -----------------------------------------------------------------------------

-- Timezone: IMD operates in IST, but everything is stored UTC and converted
-- for display only.
SET timezone = 'UTC';
