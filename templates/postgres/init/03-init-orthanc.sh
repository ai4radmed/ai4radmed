#!/bin/bash
set -e

# .env에서 ORTHANC_DB_PASSWORD를 주입받지 못한 경우 기본값 사용 (보안상 주의)
OC_PASS=${ORTHANC_DB_PASSWORD:-orthanc}
OC_USER=${ORTHANC_DB_USERNAME:-orthanc}

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER "$OC_USER" WITH PASSWORD '$OC_PASS';
    CREATE DATABASE orthanc;
    GRANT ALL PRIVILEGES ON DATABASE orthanc TO "$OC_USER";
    ALTER DATABASE orthanc OWNER TO "$OC_USER";
EOSQL
