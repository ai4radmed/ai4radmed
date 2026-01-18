#!/bin/bash
set -e

# Configuration
KC_CONTAINER="ai4radmed-keycloak"
REALM="ai4radmed"
CLIENT_ID="ai4radmed-client"
CLIENT_SECRET="change_me_in_production"
USER="ben"
PASSWORD="password"

echo "[Provisioning] Keycloak Realm '$REALM' setup..."

# 1. Login to Keycloak Admin
docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password admin

# 2. Create Realm (if not exists)
if docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh get realms/$REALM >/dev/null 2>&1; then
    echo "Realm '$REALM' already exists."
else
    echo "Creating Realm '$REALM'..."
    docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh create realms -s realm=$REALM -s enabled=true
fi

# 3. Create Client
if docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh get clients -r $REALM -q clientId=$CLIENT_ID | grep "$CLIENT_ID" >/dev/null; then
    echo "Client '$CLIENT_ID' already exists."
else
    echo "Creating Client '$CLIENT_ID'..."
    docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh create clients -r $REALM \
      -s clientId=$CLIENT_ID \
      -s enabled=true \
      -s protocol=openid-connect \
      -s publicClient=false \
      -s secret=$CLIENT_SECRET \
      -s 'redirectUris=["https://*.ai4radmed.internal/*", "http://*.ai4radmed.internal/*"]' \
      -s 'webOrigins=["+"]' \
      -s standardFlowEnabled=true \
      -s directAccessGrantsEnabled=true
fi

# 4. Create User
if docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh get users -r $REALM -q username=$USER | grep "$USER" >/dev/null; then
    echo "User '$USER' already exists."
else
    echo "Creating User '$USER'..."
    docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh create users -r $REALM -s username=$USER -s enabled=true
    docker exec $KC_CONTAINER /opt/keycloak/bin/kcadm.sh set-password -r $REALM --username $USER --new-password $PASSWORD
fi

echo "[Provisioning] Keycloak setup complete!"
