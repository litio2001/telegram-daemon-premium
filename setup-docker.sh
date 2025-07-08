#!/bin/bash
# Setup script para Telegram Download Daemon Premium
# Para uso en entorno Docker/Linux

set -e  # Exit on any error

echo "🐳 Setting up Telegram Download Daemon (Premium Enhanced) for Docker"
echo "=================================================================="

# Función para validar si una variable está configurada
check_env_var() {
    local var_name=$1
    local var_value=$(eval echo \$$var_name)
    
    if [ -z "$var_value" ] || [ "$var_value" = "YOUR API ID HERE" ] || [ "$var_value" = "YOUR API HASH HERE" ] || [ "$var_value" = "YOUR CHANNEL ID HERE" ]; then
        echo "❌ ERROR: $var_name is not properly configured"
        return 1
    else
        echo "✅ $var_name: configured"
        return 0
    fi
}

echo ""
echo "🔍 Checking required environment variables..."

# Verificar variables requeridas
ERRORS=0

check_env_var "TELEGRAM_DAEMON_API_ID" || ERRORS=$((ERRORS + 1))
check_env_var "TELEGRAM_DAEMON_API_HASH" || ERRORS=$((ERRORS + 1))
check_env_var "TELEGRAM_DAEMON_CHANNEL" || ERRORS=$((ERRORS + 1))

# Verificar variables opcionales con valores por defecto
echo ""
echo "📋 Optional environment variables:"
echo "   TELEGRAM_DAEMON_DEST: ${TELEGRAM_DAEMON_DEST:-/downloads}"
echo "   TELEGRAM_DAEMON_SESSION_PATH: ${TELEGRAM_DAEMON_SESSION_PATH:-/session}"
echo "   TELEGRAM_DAEMON_WORKERS: ${TELEGRAM_DAEMON_WORKERS:-auto}"
echo "   TELEGRAM_DAEMON_DUPLICATES: ${TELEGRAM_DAEMON_DUPLICATES:-rename}"

# Variables Premium
echo ""
echo "⭐ Premium-specific variables:"
echo "   TELEGRAM_DAEMON_PREMIUM_MAX_SIZE: ${TELEGRAM_DAEMON_PREMIUM_MAX_SIZE:-4000} MB"
echo "   TELEGRAM_DAEMON_CHUNK_SIZE: ${TELEGRAM_DAEMON_CHUNK_SIZE:-512} KB"

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "❌ Setup failed: $ERRORS required environment variable(s) not configured"
    echo ""
    echo "📖 Please configure the required variables in your docker-compose.yml:"
    echo "   - TELEGRAM_DAEMON_API_ID: Your API ID from https://core.telegram.org/api/obtaining_api_id"
    echo "   - TELEGRAM_DAEMON_API_HASH: Your API Hash from https://core.telegram.org/api/obtaining_api_id"
    echo "   - TELEGRAM_DAEMON_CHANNEL: The channel ID to download from"
    echo ""
    exit 1
fi

echo ""
echo "✅ All required variables are configured!"

# Verificar directorios y permisos
echo ""
echo "📁 Checking directories and permissions..."

DOWNLOAD_DIR="${TELEGRAM_DAEMON_DEST:-/downloads}"
SESSION_DIR="${TELEGRAM_DAEMON_SESSION_PATH:-/session}"

# Crear directorios si no existen
mkdir -p "$DOWNLOAD_DIR" || true
mkdir -p "$SESSION_DIR" || true

# Verificar permisos de escritura
if [ -w "$DOWNLOAD_DIR" ]; then
    echo "✅ Download directory writable: $DOWNLOAD_DIR"
else
    echo "⚠️  Warning: Download directory may not be writable: $DOWNLOAD_DIR"
fi

if [ -w "$SESSION_DIR" ]; then
    echo "✅ Session directory writable: $SESSION_DIR"
else
    echo "⚠️  Warning: Session directory may not be writable: $SESSION_DIR"
fi

# Mostrar información del sistema
echo ""
echo "💻 System information:"
echo "   Python version: $(python3 --version 2>/dev/null || echo 'Not available')"
echo "   OS: $(uname -s) $(uname -r)"
echo "   Architecture: $(uname -m)"

# Verificar dependencias Python
echo ""
echo "📦 Checking Python dependencies..."
python3 -c "
try:
    import telethon
    print(f'✅ Telethon: {telethon.__version__}')
except ImportError:
    print('❌ Telethon not found')

try:
    import cryptg
    print('✅ Cryptg: available')
except ImportError:
    print('⚠️  Cryptg not available (optional for faster encryption)')
"

echo ""
echo "🚀 Setup completed successfully!"
echo ""
echo "📚 Next steps:"
echo "   1. Start the daemon: docker-compose up -d"
echo "   2. For first-time setup: docker-compose run --rm telegram-download-daemon"
echo "   3. Check logs: docker-compose logs -f telegram-download-daemon"
echo ""
echo "🧪 Testing:"
echo "   - Premium detection: Run premium_test.py inside the container"
echo "   - Status check: Send 'status' message to your configured channel"
echo ""
echo "📖 For more information, see README.md and TESTING.md"
