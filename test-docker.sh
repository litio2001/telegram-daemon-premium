#!/bin/bash
# Test script para verificar que el contenedor funcione correctamente

set -e

echo "🐳 Testing Docker container build and dependencies..."

# Build the image
echo "📦 Building Docker image..."
docker build -t telegram-daemon-test .

# Test that dependencies are installed
echo "🔍 Testing Python dependencies..."
docker run --rm telegram-daemon-test python3 -c "
import sys
print(f'Python version: {sys.version}')

try:
    import telethon
    print(f'✅ Telethon version: {telethon.__version__}')
except ImportError as e:
    print(f'❌ Telethon import failed: {e}')
    sys.exit(1)

try:
    import cryptg
    print('✅ Cryptg: available')
except ImportError:
    print('⚠️  Cryptg not available (optional)')

print('✅ All critical dependencies are working!')
"

# Test that the main script can be imported (without running)
echo "🧪 Testing main script import..."
docker run --rm telegram-daemon-test python3 -c "
import sys
sys.path.append('/app')
try:
    # Test basic imports without running the daemon
    from telegram-download-daemon import *
    print('❌ Script should not import everything globally')
except:
    # This is expected - let's just check if the file is valid Python
    with open('/app/telegram-download-daemon.py', 'r') as f:
        import ast
        try:
            ast.parse(f.read())
            print('✅ Main script syntax is valid')
        except SyntaxError as e:
            print(f'❌ Syntax error in main script: {e}')
            sys.exit(1)
"

echo "🎉 Docker container test completed successfully!"
echo ""
echo "🚀 You can now use the image with:"
echo "   docker-compose up -d"
