# telegram-download-daemon (Premium Enhanced)

A Telegram Daemon (not a bot) for file downloading automation with **Premium account support** [for channels of which you have admin privileges](https://github.com/alfem/telegram-download-daemon/issues/48).

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/E1E03K0RP)

## 🚀 New Premium Features

This enhanced version includes **automatic Premium account detection** and takes advantage of Telegram Premium capabilities:

- **🔍 Automatic Premium Detection**: Detects Premium accounts using multiple methods based on official Telegram API documentation
- **📦 Large File Support**: Premium accounts can download files up to 4GB (configurable)
- **⚡ Optimized Downloads**: Enhanced chunk sizes for Premium accounts
- **💎 Smart File Handling**: Premium-specific features and optimizations

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

## 🐳 Quick Docker Setup

### 1. **Configure Environment Variables**

Edit the `docker-compose.yml` file with your credentials:

```yaml
environment:
  TELEGRAM_DAEMON_API_ID: "your_api_id"
  TELEGRAM_DAEMON_API_HASH: "your_api_hash"
  TELEGRAM_DAEMON_CHANNEL: "your_channel_id"
  # Premium settings (optional)
  TELEGRAM_DAEMON_PREMIUM_MAX_SIZE: "4000"  # MB
```

### 2. **First-Time Setup (Interactive)**

When we use the [`TelegramClient`](https://docs.telethon.dev/en/latest/quick-references/client-reference.html#telegramclient) method, it requires us to interact with the `Console` to give it our phone number and confirm with a security code.

To do this, when using *Docker*, you need to **interactively** run the container for the first time.

```bash
# Interactive first-time setup
docker-compose run --rm telegram-download-daemon
# Interact with the console to authenticate yourself.
# You'll see Premium detection information during startup
# See the message "Signed in successfully as {your name}"
# Close the container (Ctrl+C)

# Start daemon in background
docker-compose up -d
```

### ⚠️ **Permission Issues Fix**

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
  - ./downloads:/downloads
  - ./sessions:/session

# Then create directories with correct permissions:
mkdir -p downloads sessions
chmod 777 downloads sessions
```

### 3. **Monitor and Manage**

```bash
# Check logs and Premium detection
docker-compose logs -f telegram-download-daemon

# Restart daemon
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

### v1.15-Premium
- ✅ Added automatic Premium account detection
- ✅ Implemented multiple detection methods for reliability
- ✅ Enhanced file size limits for Premium accounts
- ✅ Optimized download performance for Premium users
- ✅ Added comprehensive debug logging
- ✅ Improved error handling and user feedback
