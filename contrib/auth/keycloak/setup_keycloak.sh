#!/usr/bin/env bash
set -euo pipefail

cd /opt/keycloak/bin

./kcadm.sh config credentials \
  --server "http://localhost:8080" \
  --realm master \
  --user admin \
  --password admin

./kcadm.sh create realms \
  -s realm=demorealm \
  -s enabled=true

./kcadm.sh create users \
  -r demorealm \
  -s username=testuser \
  -s firstName=Test \
  -s lastName=User \
  -s email=testuser@example.invalid \
  -s emailVerified=true \
  -s enabled=true

./kcadm.sh set-password \
  -r demorealm \
  --username testuser \
  --new-password testpass \
  --temporary=false

client_uuid="$(
  ./kcadm.sh create clients \
    -r demorealm \
    -s clientId=testclient \
    -s enabled=true \
    -s protocol=openid-connect \
    -s publicClient=true \
    -s standardFlowEnabled=true \
    -s directAccessGrantsEnabled=false \
    -s 'redirectUris=["http://localhost:8901"]' \
    -s 'attributes={"pkce.code.challenge.method":"S256"}' \
    -i
)"

./kcadm.sh create "clients/${client_uuid}/protocol-mappers/models" \
  -r demorealm \
  -s name=testclient-audience \
  -s protocol=openid-connect \
  -s protocolMapper=oidc-audience-mapper \
  -s consentRequired=false \
  -s 'config."included.client.audience"=testclient' \
  -s 'config."access.token.claim"=true' \
  -s 'config."id.token.claim"=false'

./kcadm.sh create "clients/${client_uuid}/protocol-mappers/models" \
  -r demorealm \
  -s name=testclient-roles \
  -s protocol=openid-connect \
  -s protocolMapper=oidc-usermodel-client-role-mapper \
  -s 'config."usermodel.clientRoleMapping.clientId"=testclient' \
  -s 'config."claim.name"=roles' \
  -s 'config."jsonType.label"=String' \
  -s 'config."multivalued"=true' \
  -s 'config."access.token.claim"=true' \
  -s 'config."id.token.claim"=false'

for role in admin user viewer; do
  ./kcadm.sh create "clients/${client_uuid}/roles" \
    -r demorealm \
    -s "name=${role}"
done

./kcadm.sh add-roles \
  -r demorealm \
  --uusername testuser \
  --cclientid testclient \
  --rolename user
