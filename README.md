# telegram-download-daemon v2.0 (Premium Enhanced Edition) 🚀

A Telegram Daemon (not a bot) for file downloading automation with **Premium account support** and **enhanced user experience** [for channels of which you have admin privileges](https://github.com/alfem/telegram-download-daemon/issues/48).

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/E1E03K0RP)

## ✨ What's New in v2.0

### 🎯 **Enhanced Premium Detection & Notifications**
- **Visual Premium Status on Startup**: The bot now sends a **detailed message to your Telegram channel** indicating:
  - ✅ Whether your account is Premium or Standard
  - 📊 Complete system configuration
  - ⚡ Active optimizations
  - 🔧 Technical details (workers, file limits, etc.)
- **Multiple detection methods** for maximum reliability
- **Clear visual indicators** in console and Telegram messages

### 📊 **New Statistics & Monitoring**
- **Real-time download speed** with ETA calculation
- **Session statistics**:
  - Total downloads (successful/failed)
  - Total data downloaded
  - Average speed
  - Largest file downloaded
  - Uptime and success rate
- **Download progress** now shows:
  - Current speed (MB/s)
  - Estimated time remaining (ETA)
  - Formatted sizes (KB, MB, GB)

### 🎮 **New Interactive Commands**
- `help` - Show all available commands with descriptions
- `config` - Display current configuration
- `stats` - View detailed session statistics
- `pause` - Pause download queue processing
- `resume` - Resume download queue processing
- `status` - Enhanced status with more details
- `queue` - See files waiting to be downloaded
- `list` - List downloaded files
- `clean` - Remove temporary files

### 🔄 **Improved Download Management**
- **Automatic retry system** (up to 3 attempts)
- **Smart error handling** with contextual suggestions
- **File filters** by extension (configure via `TELEGRAM_DAEMON_FILE_FILTER`)
- **Pause/Resume** functionality for queue management
- **Better duplicate handling**

### 💬 **Enhanced User Experience**
- **Beautiful formatted messages** with emojis and clear sections
- **Detailed progress updates** during downloads
- **Helpful error messages** with solutions
- **Premium upgrade suggestions** for standard users when applicable

## 🚀 Premium Features

This enhanced version includes **automatic Premium account detection** and takes advantage of Telegram Premium capabilities:

- **🔍 Automatic Premium Detection**:
  - Detects Premium accounts using multiple robust methods
  - **Sends notification to Telegram channel on startup** with your account status
  - Visual indicators throughout the application

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

- **🎯 Intelligent Error Handling**:
  - Context-aware suggestions for Standard users
  - Automatic retry system with exponential backoff

## 📋 Technical Implementation

### Premium Detection Methods
1. **Primary**: `client.get_me()` - Most reliable Telethon method
2. **Backup**: `users.getUsers` with `InputUserSelf` - Official Telegram API
3. **Fallback**: `users.getFullUser` - Complete user information

### Download Optimizations
- **Premium accounts**: Benefit from Telethon's internal Premium optimizations
- **Parallel processing**: Dynamic worker scaling based on account type and CPU cores
- **Error resilience**: Automatic retry system (3 attempts with increasing delays)
- **Connection tuning**: Optimized timeouts and retry strategies for large files
- **Real-time monitoring**: Speed calculation, ETA, and progress tracking

## Standard Features

If you have got an Internet connected computer or NAS and you want to automate file downloading from Telegram channels, this daemon is for you.

Telegram bots are limited to 20Mb file size downloads. This daemon allows bigger downloads:
- **Standard accounts**: Limited to 2GB by Telegram APIs
- **Premium accounts**: Up to 4GB (or custom limit)

# Installation

You need Python3 (3.6 works fine, 3.5 will crash randomly).

Install dependencies by running this command:

    pip install -r requirements.txt

(If you don't want to install `cryptg` and its dependencies, you just need to install `telethon`)

Warning: If you get a `File size too large message`, check the version of Telethon library you are using. Old versions have got a 1.5Gb file size limit.

Obtain your own api id: https://core.telegram.org/api/obtaining_api_id

# Configuration

## Environment Variables

| Environment Variable     | Command Line argument | Description                                                  | Default Value       |
|--------------------------|:-----------------------:|--------------------------------------------------------------|---------------------|
| `TELEGRAM_DAEMON_API_ID`   | `--api-id`              | api_id from https://core.telegram.org/api/obtaining_api_id   |                     |
| `TELEGRAM_DAEMON_API_HASH` | `--api-hash`            | api_hash from https://core.telegram.org/api/obtaining_api_id |                     |
| `TELEGRAM_DAEMON_DEST`     | `--dest`                | Destination path for downloaded files                       | `/telegram-downloads` |
| `TELEGRAM_DAEMON_TEMP`     | `--temp`                | Destination path for temporary (download in progress) files                       | use --dest |
| `TELEGRAM_DAEMON_CHANNEL`  | `--channel`             | Channel id to download from it                             |                     |
| `TELEGRAM_DAEMON_DUPLICATES`  | `--duplicates`             | What to do with duplicated files: ignore, overwrite or rename them | rename                     |
| `TELEGRAM_DAEMON_WORKERS`  | `--workers`             | Number of simultaneous downloads | Equals to processor cores                     |
| `TELEGRAM_DAEMON_PREMIUM_MAX_SIZE` | (env only) | Maximum file size for Premium accounts (MB) | 4000 |
| `TELEGRAM_DAEMON_FILE_FILTER` | (env only) | Filter files by extension (comma-separated, e.g., "mp4,mkv,avi") | (no filter) |

## 🔧 Premium Configuration

For Premium accounts, you can configure additional settings:

```bash
export TELEGRAM_DAEMON_PREMIUM_MAX_SIZE=4000  # Max file size in MB for Premium (default: 4000)
export TELEGRAM_DAEMON_FILE_FILTER="mp4,mkv,avi,mp3"  # Only download these file types
```

## Usage Example

You can define them as Environment Variables, or put them as command line arguments, for example:

    python telegram-download-daemon.py --api-id <your-id> --api-hash <your-hash> --channel <channel-number>

# Using the Daemon

## First Run

When you start the daemon for the first time:

1. **Authentication**: You'll need to enter your phone number and verification code
2. **Premium Detection**: The daemon will automatically detect if you have Telegram Premium
3. **Welcome Message**: You'll receive a **detailed message in your Telegram channel** showing:
   - Your account type (Premium ⭐ or Standard 📱)
   - File size limits
   - Active optimizations
   - Number of parallel workers
   - All configuration details

## Downloading Files

Simply **forward or resend any file** to the configured channel and the daemon will:
1. Add it to the download queue
2. Show download progress with speed and ETA
3. Notify you when completed
4. Store it in the configured download folder

## 📝 Available Commands

Send these commands as text messages to your channel:

### Information Commands
- **`help`** - Show all available commands with descriptions
- **`status`** - View active downloads and account information
- **`config`** - Display current configuration settings
- **`stats`** - View detailed session statistics (downloads, speed, data transferred)

### Queue Management
- **`queue`** - See files waiting in the download queue
- **`pause`** - Pause processing new downloads (current downloads continue)
- **`resume`** - Resume processing the download queue

### File Management
- **`list`** - List all downloaded files in the destination folder
- **`clean`** - Remove temporary (*.tdd) files from temp directory

## Example Workflow

```
1. Start daemon → Receive welcome message with Premium/Standard status
2. Forward file to channel → File added to queue notification
3. Download starts → Progress updates with speed/ETA
4. Download completes → Completion notification with statistics
5. Send "stats" → View session statistics
```

## 🚑 Troubleshooting

### Welcome Message Not Received

If you do **not** receive the detailed welcome message in your Telegram channel after starting the daemon:

1. **Verify Channel ID**
   - Double-check that you provided the correct channel ID (should be a negative number, e.g., `-1001234567890`)
   - You can obtain the channel ID by forwarding a message from your channel to [@userinfobot](https://t.me/userinfobot)

2. **Check Permissions**
   - Ensure the account running the daemon is an **admin** in the channel
   - The account must have permission to **post messages** in the channel

3. **Manually Trigger Welcome Message**
   - Restart the daemon to trigger the welcome message again
   - Send `status` as a message in the channel to verify the daemon is responding

4. **Check Logs**
   - Review the daemon's console output for any errors or warnings related to channel access or message sending
   - Look for connection errors or authentication issues

### File Filter Not Working

If file filters (`TELEGRAM_DAEMON_FILE_FILTER`) are not working:

- Ensure extensions are provided **without dots** (e.g., `mp4,mkv,avi` not `.mp4,.mkv,.avi`)
- Extensions are case-insensitive
- Restart the daemon after changing the filter configuration

### Downloads Not Starting

If downloads are added to queue but don't start:

- Check if the queue is paused (send `status` command to verify)
- Send `resume` if downloads are paused
- Verify you have sufficient disk space in the download directory
- Check console logs for error messages

# Docker (Premium Enhanced)

`docker pull alfem/telegram-download-daemon`

## 🐳 Quick Docker Setup

### 1. **Configure Environment Variables**

Edit the `docker-compose.yml` file with your credentials:

```yaml
environment:
  TELEGRAM_DAEMON_API_ID: "YOUR_API_ID"
  TELEGRAM_DAEMON_API_HASH: "YOUR_API_HASH"
  TELEGRAM_DAEMON_CHANNEL: "YOUR_CHANNEL_ID"
  # Premium configuration (optional)
  TELEGRAM_DAEMON_PREMIUM_MAX_SIZE: "4000"  # MB
  TELEGRAM_DAEMON_FILE_FILTER: "mp4,mkv,avi"  # Optional: filter by extension
```

### 2. **First Run (Interactive)**

**IMPORTANT:**
The **first time** you run the container, you must launch it **interactively** to enter your phone number and verification code:

```bash
# Interactive initial run (required first time)
docker-compose run --rm telegram-download-daemon
# Follow the on-screen instructions:
# 1. Enter your phone number
# 2. Enter the verification code from Telegram app
# 3. Wait for the welcome message and Premium detection
# 4. When you see "Signed in successfully", you can close (Ctrl+C)
```

After this step, the session is saved and you can run the daemon in background:

```bash
# Launch daemon in background mode
docker-compose up -d
```

### 3. **Running the Script Manually**

If you need to run the main script directly inside the container:

```bash
docker-compose exec telegram-download-daemon python3 telegram-download-daemon.py
```

### ⚠️ **Permission Issues Solution**

If you get permission errors like `Permission denied: '/session/DownloadDaemon.session'`:

```bash
# Option 1: Fix volume permissions (Linux/macOS)
sudo chown -R 1000:1000 /var/lib/docker/volumes/

# Option 2: Use bind mounts instead of volumes
# Edit docker-compose.yml and replace:
volumes:
  - downloads:/downloads
  - sessions:/session
# With:
volumes:
  - ./downloads:/downloads
  - ./sessions:/session

# Then create directories with correct permissions:
mkdir -p downloads sessions
chmod 777 downloads sessions
```

### 4. **Monitoring and Management**

```bash
# View logs and Premium detection
docker-compose logs -f telegram-download-daemon

# Restart the daemon
docker-compose restart telegram-download-daemon

# Stop the daemon
docker-compose down
```

## 🎯 What You'll See on Startup

When the daemon starts, you'll receive a message in your Telegram channel like this:

```
==================================================
🚀 TELEGRAM DOWNLOAD DAEMON
📦 Versión 2.0-Premium-Enhanced
==================================================

🔧 INFORMACIÓN DEL SISTEMA
├─ 📚 Telethon: 1.36.0
├─ 🐍 Python Asyncio
├─ 🖥️  CPU Cores: 4
└─ 📅 Inicio: 2025-01-15 10:30:45

──────────────────────────────────────────────────
🌟 CUENTA PREMIUM DETECTADA 🌟
──────────────────────────────────────────────────

👤 ESTADO DE CUENTA
├─ ⭐ Tipo: Premium
├─ 📁 Límite de archivo: 4,000 MB
└─ 🔄 Workers paralelos: 12

✨ CARACTERÍSTICAS ACTIVAS
✅ Archivos hasta 4GB
✅ Sin límites de velocidad
✅ Descarga optimizada
✅ Prioridad en servidores
✅ Workers paralelos mejorados

🎯 OPTIMIZACIONES PREMIUM
⚡ Sin límites FLOOD_WAIT
📦 Chunks de 1MB para grandes archivos
🚀 Paralelismo x3 mejorado
💎 Prioridad en servidores Telegram

⚙️  CONFIGURACIÓN
├─ 📂 Destino: /downloads
├─ 🔄 Duplicados: rename
└─ 💾 Temporal: /downloads

📝 COMANDOS DISPONIBLES
└─ Escribe help para ver todos los comandos

==================================================
✅ SISTEMA LISTO PARA DESCARGAS
==================================================
```

# 📊 Feature Comparison

| Feature | Standard Account | Premium Account |
|---------|-----------------|-----------------|
| Max File Size | 2 GB | 4 GB (configurable) |
| Download Speed | Limited (FLOOD_WAIT) | Unlimited |
| Parallel Workers | CPU cores x1 | CPU cores x3 (max 12) |
| Chunk Size | Standard | Optimized (1MB) |
| Server Priority | Normal | Premium priority |
| Retry System | ✅ 3 attempts | ✅ 3 attempts |
| Real-time Speed | ✅ Yes | ✅ Yes |
| Statistics | ✅ Yes | ✅ Yes |
| File Filters | ✅ Yes | ✅ Yes |
| Pause/Resume | ✅ Yes | ✅ Yes |

# 📝 Changelog

## v2.0.1-premium-enhanced (Latest) 🛡️

### 🔒 Security & Thread-Safety Improvements
- **Thread-safe operations**: Added `asyncio.Lock()` for all shared data structures (stats, progress tracking)
- **Event-based pause/resume**: Replaced global variable with `asyncio.Event()` for proper synchronization
- **Eliminated shell injection risks**: Removed `shell=True` from all subprocess calls
  - `list` command: Now uses `subprocess.run(["ls", "-lh", downloadFolder])`
  - `clean` command: Uses `glob` and `os.remove()` instead of shell commands

### 🐛 Bug Fixes
- **Fixed file extension parsing**: Now uses `os.path.splitext()` for robust extension extraction
- **Corrected statistics counting**: Moved `total_downloads` increment to worker (when download starts, not when queued)
- **Better exception handling**: Replaced bare `except:` with `except Exception:` throughout codebase
- **Memory optimization**: Limited `download_speeds` to 1000 entries using `deque(maxlen=1000)`

### 📏 Code Quality Improvements
- **Semantic versioning**: Updated version format to `2.0.1-premium-enhanced` (semver compliant)
- **Named constants**: Defined constants for magic numbers:
  - `SPEED_SAMPLES_FOR_AVERAGE = 10`
  - `MAX_DOWNLOAD_SPEEDS = 1000`
  - `MAX_RETRIES = 3`
  - `RETRY_DELAY_BASE = 5`
- **Linear backoff clarification**: Added comment explaining retry delay is linear (5s, 10s, 15s), not exponential

### 📚 Documentation
- **Troubleshooting section**: Added comprehensive troubleshooting guide for common issues
- **File filter clarification**: Documented that extensions should be without dots (e.g., `mp4` not `.mp4`)

## v2.0.0-premium-enhanced 🎉

### 🌟 Major New Features
- **✨ Visual Premium Status Notification**: Clear message sent to Telegram channel on startup indicating Premium/Standard status
- **📊 Real-time Statistics**: Complete session stats with downloads, speed, data transferred
- **🎮 Interactive Commands**: 9 new commands (help, config, stats, pause, resume, and more)
- **⚡ Speed Monitoring**: Real-time download speed with ETA calculation
- **🔄 Auto-retry System**: Automatic retry up to 3 times with exponential backoff
- **🎯 File Filters**: Filter downloads by file extension

### 💬 Enhanced User Experience
- **Beautiful formatted messages** with clear sections and emojis
- **Detailed progress updates** showing speed, ETA, and formatted sizes
- **Contextual error messages** with helpful solutions
- **Premium upgrade suggestions** for standard users
- **Helper functions** for formatting bytes, speed, and time

### 🔧 Technical Improvements
- Better code organization with utility functions
- Enhanced statistics tracking (speeds, largest file, success rate)
- Improved error handling with specific suggestions
- Queue pause/resume functionality
- Session uptime tracking

### 🐛 Bug Fixes
- Fixed global variable declarations
- Improved download progress tracking
- Better handling of temporary files
- Enhanced duplicate file detection

## v1.17-Premium
- 🔧 Fixed Premium detection with simplified method
- ⚡ Corrected download optimizations
- 🚀 Improved client configuration
- 💡 Enhanced UX/UI with better messages

## v1.16-Premium
- 🚀 Multiple Premium detection methods
- ⚡ Speed optimizations for Premium
- 💎 Improved interface

## v1.15-Premium
- ✅ Added automatic Premium account detection
- ✅ Enhanced file size limits for Premium accounts
- ✅ Improved error handling

# 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

# 📄 License

This project maintains the same license as the original telegram-download-daemon.

# ⭐ Support

If you find this project useful, consider:
- Starring the repository
- Supporting the original author: [![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/E1E03K0RP)
- Sharing with others who might benefit

# 🔗 Links

- **Original Project**: [telegram-download-daemon](https://github.com/alfem/telegram-download-daemon)
- **Telegram API Documentation**: https://core.telegram.org/api
- **Telethon Documentation**: https://docs.telethon.dev/
- **Telegram Premium**: https://telegram.org/premium
