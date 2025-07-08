# telegram-download-daemon (Premium Enhanced)

A Telegram Daemon (not a bot) for file downloading automation with **Premium account support** [for channels of which you have admin privileges](https://github.com/alfem/telegram-download-daemon/issues/48).

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/E1E03K0RP)

## 🚀 New Premium Features

This enhanced version includes **automatic Premium account detection** and takes advantage of Telegram Premium capabilities:

- **🔍 Automatic Premium Detection**: Detects Premium accounts using multiple robust methods based on official Telegram API documentation
- **📦 Large File Support**: Premium accounts can download files up to 4GB (configurable)
- **⚡ Optimized Downloads**: 
  - Telethon's internal Premium optimizations automatically activated
  - Dynamic worker scaling (up to 12 workers for Premium vs 4 for Standard)
  - Enhanced connection parameters (retry_delay, timeout, connection_retries)
  - No download speed limits (FLOOD_PREMIUM_WAIT_X exemption)
- **💎 Smart Configuration**: 
  - CPU-based worker scaling (Premium: CPU cores x3, Standard: CPU cores x1)
  - Automatic chunk size optimization handled by Telethon internally
  - Premium-specific client identification for better server treatment
- **🎯 Intelligent Error Handling**: Context-aware suggestions for Standard users

## Technical Implementation

### Premium Detection Methods
1. **Primary**: `client.get_me()` - Most reliable Telethon method
2. **Backup**: `users.getUsers` with `InputUserSelf` - Official Telegram API
3. **Fallback**: `users.getFullUser` - Complete user information  
4. **Verification**: `help.getPremiumPromo` - Cross-validation

### Download Optimizations
- **Premium accounts**: Benefit from Telethon's internal Premium optimizations
- **Parallel processing**: Dynamic worker scaling based on account type and CPU cores
- **Error resilience**: Automatic fallback to standard methods if optimizations fail
- **Connection tuning**: Optimized timeouts and retry strategies for large files

## Standard Features

If you have got an Internet connected computer or NAS and you want to automate file downloading from Telegram channels, this
daemon is for you.

Telegram bots are limited to 20Mb file size downloads. So I wrote this agent
or daemon to allow bigger downloads:
- **Standard accounts**: Limited to 2GB by Telegram APIs
- **Premium accounts**: Up to 4GB (or custom limit)

# Installation

You need Python3 (3.6 works fine, 3.5 will crash randomly).

Install dependencies by running this command:

    pip install -r requirements.txt

(If you don't want to install `cryptg` and its dependencies, you just need to install `telethon`)

Warning: If you get a `File size too large message`, check the version of Telethon library you are using. Old versions have got a 1.5Gb file size limit.


Obtain your own api id: https://core.telegram.org/api/obtaining_api_id

# Usage

You need to configure these values:

| Environment Variable     | Command Line argument | Description                                                  | Default Value       |
|--------------------------|:-----------------------:|--------------------------------------------------------------|---------------------|
| `TELEGRAM_DAEMON_API_ID`   | `--api-id`              | api_id from https://core.telegram.org/api/obtaining_api_id   |                     |
| `TELEGRAM_DAEMON_API_HASH` | `--api-hash`            | api_hash from https://core.telegram.org/api/obtaining_api_id |                     |
| `TELEGRAM_DAEMON_DEST`     | `--dest`                | Destination path for downloaded files                       | `/telegram-downloads` |
| `TELEGRAM_DAEMON_TEMP`     | `--temp`                | Destination path for temporary (download in progress) files                       | use --dest |
| `TELEGRAM_DAEMON_CHANNEL`  | `--channel`             | Channel id to download from it (Please, check [Issue 45](https://github.com/alfem/telegram-download-daemon/issues/45), [Issue 48](https://github.com/alfem/telegram-download-daemon/issues/48) and [Issue 73](https://github.com/alfem/telegram-download-daemon/issues/73))                              |                     |
| `TELEGRAM_DAEMON_DUPLICATES`  | `--duplicates`             | What to do with duplicated files: ignore, overwrite or rename them | rename                     |
| `TELEGRAM_DAEMON_WORKERS`  | `--workers`             | Number of simultaneous downloads | Equals to processor cores                     |
| `TELEGRAM_DAEMON_PREMIUM_MAX_SIZE` | (env only) | Maximum file size for Premium accounts (MB) | 4000 |

## 🔧 Premium Configuration

For Premium accounts, you can configure additional settings:

```bash
export TELEGRAM_DAEMON_PREMIUM_MAX_SIZE=4000  # Max file size in MB for Premium (default: 4000)
```

You can define them as Environment Variables, or put them as a command line arguments, for example:

    python telegram-download-daemon.py --api-id <your-id> --api-hash <your-hash> --channel <channel-number>


Finally, resend any file link to the channel to start the downloading. This daemon can manage many downloads simultaneously.

You can also 'talk' to this daemon using your Telegram client:

* Say "list" and get a list of available files in the destination path.
* Say "status" to the daemon to check the current status.
* Say "clean" to remove stale (*.tdd) files from temporary directory.
* Say "queue" to list the pending files waiting to start.



# Docker (Premium Enhanced)

`docker pull alfem/telegram-download-daemon`

## 🐳 Configuración rápida con Docker

### 1. **Configura las variables de entorno**

Edita el archivo `docker-compose.yml` con tus credenciales:

```yaml
environment:
  TELEGRAM_DAEMON_API_ID: "tu_api_id"
  TELEGRAM_DAEMON_API_HASH: "tu_api_hash"
  TELEGRAM_DAEMON_CHANNEL: "tu_channel_id"
  # Configuración Premium (opcional)
  TELEGRAM_DAEMON_PREMIUM_MAX_SIZE: "4000"  # MB
```

### 2. **Primer inicio (interactivo)**

**IMPORTANTE:**  
La **primera vez** que ejecutes el contenedor, debes lanzarlo de forma **interactiva** para que el sistema te solicite tu número de teléfono y puedas introducir el código de seguridad que recibirás en la app de Telegram de tu móvil.

Esto es necesario para autorizar la sesión y vincular tu cuenta de Telegram con el daemon.

```bash
# Ejecución interactiva inicial (imprescindible la primera vez)
docker-compose run --rm telegram-download-daemon
# Sigue las instrucciones en pantalla:
# 1. Introduce tu número de teléfono.
# 2. Introduce el código de seguridad recibido en tu app de Telegram.
# 3. Espera a ver el mensaje de bienvenida y la detección de Premium.
# 4. Cuando veas "Signed in successfully as {tu nombre}", puedes cerrar el contenedor (Ctrl+C).
```

Después de este paso, la sesión queda guardada y puedes lanzar el daemon en segundo plano normalmente:

```bash
# Lanzar el daemon en modo background
docker-compose up -d
```

### 3. **Cómo ejecutar el script manualmente**

Si necesitas ejecutar el script principal directamente dentro del contenedor (por ejemplo, para depuración o pruebas), usa:

```bash
docker-compose exec telegram-download-daemon app telegram-download-daemon.py
```

O, si el contenedor ya tiene Python en el PATH:

```bash
docker-compose exec telegram-download-daemon python3 telegram-download-daemon.py
```

### ⚠️ **Solución de problemas de permisos**

Si obtienes errores de permisos como `Permission denied: '/session/DownloadDaemon.session'`:

```bash
# Opción 1: Corrige los permisos de los volúmenes (Linux/macOS)
sudo chown -R 1000:1000 /var/lib/docker/volumes/

# Opción 2: Usa bind mounts en vez de volúmenes
# Edita docker-compose.yml y reemplaza:
volumes:
  - downloads:/downloads
  - sessions:/session
# Por:
  - ./downloads:/downloads
  - ./sessions:/session

# Luego crea los directorios con los permisos correctos:
mkdir -p downloads sessions
chmod 777 downloads sessions
```

### 4. **Monitorización y gestión**

```bash
# Ver logs y detección de Premium
docker-compose logs -f telegram-download-daemon

# Reiniciar el daemon
docker-compose restart telegram-download-daemon
```

## 🔧 Docker Premium Configuration

The `docker-compose.yml` includes Premium-specific environment variables:

```yaml
environment:
  # Standard configuration
  TELEGRAM_DAEMON_API_ID: "YOUR API ID HERE"
  TELEGRAM_DAEMON_API_HASH: "YOUR API HASH HERE"
  TELEGRAM_DAEMON_CHANNEL: "YOUR CHANNEL ID HERE"
  TELEGRAM_DAEMON_DEST: "/downloads"
  TELEGRAM_DAEMON_SESSION_PATH: "/session"
  
  # Premium-specific settings
  TELEGRAM_DAEMON_PREMIUM_MAX_SIZE: "4000"  # Max file size in MB
```

See the `sessions` volume in the [docker-compose.yml](docker-compose.yml) file.

## 🔍 Premium Detection Implementation

This enhanced version uses a robust Premium detection system based on the official Telegram API documentation:

### Detection Methods

1. **Direct Attribute Check**: Uses the `premium` attribute from the User object (flags.28)
2. **Flag Bit Verification**: Manually checks bit 28 in the user flags (as per MTProto schema)
3. **GetFullUserRequest Fallback**: Alternative method for edge cases
4. **Debug Information**: Comprehensive logging for troubleshooting

### Premium Benefits

- **File Size Limits**:
  - Standard: 2GB maximum
  - Premium: 4GB maximum (configurable up to higher limits)
- **Download Performance**:
  - Optimized chunk sizes for Premium accounts
  - Better handling of large files
- **Smart Error Handling**:
  - Premium-specific error messages
  - Helpful suggestions for Standard users

### Technical Implementation

The implementation follows the official Telegram API schema where Premium accounts have the `premium` flag set to `true` in the User constructor:

```
user#83314fca flags:# ... premium:flags.28?true ... = User;
```

This ensures compatibility with the latest Telegram API and reliable Premium detection.

## 📝 Changelog

### v1.17-Premium (Latest) - Correcciones Críticas
- 🔧 **Corrección de detección Premium:**
  - Simplificado método `check_premium_status` eliminando imports problemáticos
  - Priorizado `client.get_me()` como método principal (más confiable)
  - Conservados métodos de respaldo API oficial con mejor manejo de errores
  - Mejorado logging para debugging de estado Premium
- ⚡ **Optimizaciones de descarga corregidas:**
  - Eliminado uso problemático de `download_file` con parámetros incorrectos  
  - Optimizado `download_media` para aprovechar optimizaciones internas de Telethon Premium
  - Mejorado manejo de chunks automático basado en tipo de cuenta
  - Workers escalados dinámicamente hasta 12 para cuentas Premium
- 🚀 **Configuración de cliente mejorada:**
  - Añadidos parámetros de conexión optimizados (retry_delay, timeout, connection_retries)
  - Identificación específica como "TDD Premium" para mejor rendimiento
  - Configuración automática de paralelismo según CPU cores
- 💡 **UX/UI mejorada:**
  - Mensajes de bienvenida más informativos y claros
  - Estado detallado de optimizaciones Premium activas
  - Información técnica precisa sobre configuración aplicada

### v1.16-Premium
- 🚀 **Mejoras importantes en detección Premium:**
  - Implementados múltiples métodos de detección basados en API oficial
  - Uso de `users.getUsers` con `InputUserSelf` (método recomendado)
  - Fallback con `users.getFullUser` para máxima compatibilidad
  - Verificación cruzada con `help.getPremiumPromo`
- ⚡ **Optimizaciones de velocidad para Premium:**
  - Chunks de 1MB para cuentas Premium (vs 512KB estándar)
  - Workers dinámicos aumentados automáticamente
  - Uso de `download_file` optimizado para archivos grandes
- 💎 **Interfaz mejorada:**
  - Mensajes informativos mejorados
  - Estado detallado de cuenta Premium
  - Información de descarga más clara
  - Sugerencias inteligentes para usuarios estándar

### v1.15-Premium
- ✅ Added automatic Premium account detection
- ✅ Implemented multiple detection methods for reliability
- ✅ Enhanced file size limits for Premium accounts
- ✅ Optimized download performance for Premium users
- ✅ Added comprehensive debug logging
- ✅ Improved error handling and user feedback
