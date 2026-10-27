# Keycloak Testing Environment

Upstream Labgrid require a testing environment for the Labgrid AuthN/Z functionality.

## Deploy and Configure

### Start the Keycloak dev server

```shell
docker run \
  --rm \
  --name keycloak-dev \
  -p 127.0.0.1:8080:8080 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
  -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  -v "$(pwd)/contrib/auth/keycloak/setup_keycloak.sh:/setup_keycloak.sh" \
  quay.io/keycloak/keycloak:26.8.0 \
  start-dev
```

### Setup the Keycloak configuration

```shell
docker exec -it keycloak-dev bash /setup_keycloak.sh
```

### Run the interactive plugin test

```shell
KEYCLOAK_TEST=true pytest -s tests/test_auth_plugin_keycloak.py
```

The test prints the login URL.
Open the login URL in your browser.
Login with `testuser` and `testpass`.
