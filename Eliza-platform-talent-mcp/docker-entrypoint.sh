#!/bin/bash
set -e

# Load API key from Docker secret if available
if [ -f /run/secrets/eliza_api_key ]; then
    export ELIZA_API_KEY=$(cat /run/secrets/eliza_api_key)
    echo "✅ Loaded API key from Docker secret"
elif [ -n "$ELIZA_API_KEY" ]; then
    echo "✅ Using API key from environment variable"
elif [ -f /run/secrets/eliza_email ] && [ -f /run/secrets/eliza_password ]; then
    export ELIZA_EMAIL=$(cat /run/secrets/eliza_email)
    export ELIZA_PASSWORD=$(cat /run/secrets/eliza_password)
    echo "⚠️ Using legacy email/password from Docker secrets"
elif [ -n "$ELIZA_EMAIL" ] && [ -n "$ELIZA_PASSWORD" ]; then
    echo "⚠️ Using legacy email/password from environment variables"
else
    echo "❌ No authentication configured!"
    echo "   Please provide either:"
    echo "   - Docker secret: /run/secrets/eliza_api_key"
    echo "   - Environment variable: ELIZA_API_KEY"
    echo "   - Legacy: ELIZA_EMAIL + ELIZA_PASSWORD"
fi

# Execute the command
exec "$@"

