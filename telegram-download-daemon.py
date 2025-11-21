#!/usr/bin/env python3
# Telegram Download Daemon - Enhanced Premium Edition
# Original Author: Alfonso E.M. <alfonso@el-magnifico.org>
# Enhanced with Premium features and improved UX
# Version: 2.0-Premium-Enhanced

from os import getenv, path
from shutil import move
import subprocess
import math
import time
import random
import string
import os.path
from mimetypes import guess_extension
from datetime import datetime
from collections import defaultdict, deque
import glob

from sessionManager import getSession, saveSession

from telethon import TelegramClient, events, __version__
from telethon.tl.types import PeerChannel, DocumentAttributeFilename, DocumentAttributeVideo
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s]%(name)s:%(message)s',
                    level=logging.WARNING)

import multiprocessing
import argparse
import asyncio


TDD_VERSION="2.0.0-premium-enhanced"  # Nueva versión con mejoras significativas (semver)

# Constantes de configuración
SPEED_SAMPLES_FOR_AVERAGE = 10  # Número de muestras de velocidad para calcular promedio
MAX_DOWNLOAD_SPEEDS = 1000  # Máximo de velocidades almacenadas para evitar consumo excesivo de memoria
MAX_RETRIES = 3  # Número máximo de reintentos para descargas fallidas
RETRY_DELAY_BASE = 5  # Segundos base para cálculo de delay entre reintentos (linear backoff)

TELEGRAM_DAEMON_API_ID = getenv("TELEGRAM_DAEMON_API_ID")
TELEGRAM_DAEMON_API_HASH = getenv("TELEGRAM_DAEMON_API_HASH")
TELEGRAM_DAEMON_CHANNEL = getenv("TELEGRAM_DAEMON_CHANNEL")

TELEGRAM_DAEMON_SESSION_PATH = getenv("TELEGRAM_DAEMON_SESSION_PATH")

TELEGRAM_DAEMON_DEST=getenv("TELEGRAM_DAEMON_DEST", "/telegram-downloads")
TELEGRAM_DAEMON_TEMP=getenv("TELEGRAM_DAEMON_TEMP", "")
TELEGRAM_DAEMON_DUPLICATES=getenv("TELEGRAM_DAEMON_DUPLICATES", "rename")

TELEGRAM_DAEMON_TEMP_SUFFIX="tdd"

TELEGRAM_DAEMON_WORKERS=getenv("TELEGRAM_DAEMON_WORKERS", multiprocessing.cpu_count())

# Variables de entorno Premium
TELEGRAM_DAEMON_PREMIUM_MAX_SIZE=getenv("TELEGRAM_DAEMON_PREMIUM_MAX_SIZE", "4000")  # MB

# Filtros de archivo (opcional)
TELEGRAM_DAEMON_FILE_FILTER=getenv("TELEGRAM_DAEMON_FILE_FILTER", "")  # ej: "mp4,mkv,avi"

# Variables globales
is_premium_account = False
max_file_size = 2000  # MB por defecto

# Estadísticas globales
stats = {
    'total_downloads': 0,
    'successful_downloads': 0,
    'failed_downloads': 0,
    'total_bytes': 0,
    'session_start': datetime.now(),
    'largest_file': {'name': '', 'size': 0},
    'download_speeds': deque(maxlen=MAX_DOWNLOAD_SPEEDS)  # Usar deque con límite para evitar consumo excesivo de memoria
}

# Locks y eventos para sincronización entre workers
stats_lock = None  # Se inicializará en start() con asyncio.Lock()
progress_lock = None  # Se inicializará en start() con asyncio.Lock()
download_pause_event = None  # Se inicializará en start() con asyncio.Event()

parser = argparse.ArgumentParser(
    description="Script to download files from a Telegram Channel.")
parser.add_argument(
    "--api-id",
    required=TELEGRAM_DAEMON_API_ID == None,
    type=int,
    default=TELEGRAM_DAEMON_API_ID,
    help=
    'api_id from https://core.telegram.org/api/obtaining_api_id (default is TELEGRAM_DAEMON_API_ID env var)'
)
parser.add_argument(
    "--api-hash",
    required=TELEGRAM_DAEMON_API_HASH == None,
    type=str,
    default=TELEGRAM_DAEMON_API_HASH,
    help=
    'api_hash from https://core.telegram.org/api/obtaining_api_id (default is TELEGRAM_DAEMON_API_HASH env var)'
)
parser.add_argument(
    "--dest",
    type=str,
    default=TELEGRAM_DAEMON_DEST,
    help=
    'Destination path for downloaded files (default is /telegram-downloads).')
parser.add_argument(
    "--temp",
    type=str,
    default=TELEGRAM_DAEMON_TEMP,
    help=
    'Destination path for temporary files (default is using the same downloaded files directory).')
parser.add_argument(
    "--channel",
    required=TELEGRAM_DAEMON_CHANNEL == None,
    type=int,
    default=TELEGRAM_DAEMON_CHANNEL,
    help=
    'Channel id to download from it (default is TELEGRAM_DAEMON_CHANNEL env var'
)
parser.add_argument(
    "--duplicates",
    choices=["ignore", "rename", "overwrite"],
    type=str,
    default=TELEGRAM_DAEMON_DUPLICATES,
    help=
    '"ignore"=do not download duplicated files, "rename"=add a random suffix, "overwrite"=redownload and overwrite.'
)
parser.add_argument(
    "--workers",
    type=int,
    default=TELEGRAM_DAEMON_WORKERS,
    help=
    'number of simultaneous downloads'
)
args = parser.parse_args()

api_id = args.api_id
api_hash = args.api_hash
channel_id = args.channel
downloadFolder = args.dest
tempFolder = args.temp
duplicates=args.duplicates
worker_count = args.workers
updateFrequency = 10
lastUpdate = 0

if not tempFolder:
    tempFolder = downloadFolder

# Edit these lines:
proxy = None

# End of interesting parameters

def format_bytes(bytes_size):
    """Formatea bytes a formato legible (KB, MB, GB)"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def format_speed(bytes_per_second):
    """Formatea velocidad de descarga"""
    return f"{format_bytes(bytes_per_second)}/s"

def format_time(seconds):
    """Formatea tiempo en formato legible"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

def configure_client_for_premium(is_premium):
    """
    Configura parámetros optimizados del cliente según el tipo de cuenta.
    """
    global worker_count

    if is_premium:
        print("\n" + "="*60)
        print("🌟 MODO PREMIUM ACTIVADO 🌟")
        print("="*60)

        original_workers = worker_count
        worker_count = min(12, max(6, multiprocessing.cpu_count() * 3))

        print(f"✨ Optimizaciones Premium habilitadas:")
        print(f"   🔄 Workers paralelos: {original_workers} → {worker_count}")
        print(f"   ⚡ Sin límites de velocidad (FLOOD_PREMIUM_WAIT_X exento)")
        print(f"   📦 Archivos hasta {max_file_size} MB (vs 2000 MB estándar)")
        print(f"   🎯 Chunks optimizados: 1MB para archivos grandes")
        print(f"   🚀 Paralelismo mejorado para múltiples archivos")
        print(f"   💎 Prioridad Premium en servidores de Telegram")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("📱 MODO ESTÁNDAR ACTIVADO")
        print("="*60)
        print(f"⚙️  Configuración aplicada:")
        print(f"   📦 Archivos hasta {max_file_size} MB")
        print(f"   ⚡ Velocidad estándar (con límites FLOOD_WAIT)")
        print(f"   🔄 Workers: {worker_count}")
        print(f"\n💡 ¿Sabías que Telegram Premium ofrece?")
        print(f"   • Archivos hasta 4GB")
        print(f"   • Velocidad de descarga sin límites")
        print(f"   • Prioridad en servidores")
        print(f"   • Más workers paralelos")
        print(f"   📎 https://telegram.org/premium")
        print("="*60 + "\n")

async def check_premium_status(client):
    """
    Verifica si la cuenta actual es Premium usando métodos oficiales.
    Usa múltiples métodos de fallback para máxima compatibilidad.
    """
    print("\n🔍 Iniciando detección de estado Premium...")
    print("-" * 60)

    try:
        # Método 1: get_me() - Método principal y más confiable
        me = await client.get_me()
        user_name = f"{getattr(me, 'first_name', 'Unknown')} {getattr(me, 'last_name', '')}".strip()
        print(f"👤 Usuario: {user_name}")
        print(f"🆔 ID: {me.id}")
        print(f"📱 Teléfono: {getattr(me, 'phone', 'N/A')}")

        # Verificar atributo premium
        if hasattr(me, 'premium') and me.premium is True:
            print("✅ PREMIUM DETECTADO - Método: client.get_me()")
            print("-" * 60)
            return True

        premium_attr = getattr(me, 'premium', None)
        print(f"🔍 Atributo premium: {premium_attr}")

    except Exception as e:
        print(f"⚠️  get_me() falló: {e}")

    try:
        # Método 2: API oficial users.getUsers
        from telethon.tl.functions.users import GetUsersRequest
        from telethon.tl.types import InputUserSelf

        users_result = await client(GetUsersRequest([InputUserSelf()]))
        if users_result and len(users_result) > 0:
            user = users_result[0]
            premium_status = getattr(user, 'premium', None)
            print(f"🔍 Método GetUsersRequest - Premium: {premium_status}")

            if premium_status is True:
                print("✅ PREMIUM DETECTADO - Método: GetUsersRequest")
                print("-" * 60)
                return True

    except Exception as e:
        print(f"⚠️  GetUsersRequest falló: {e}")

    try:
        # Método 3: GetFullUserRequest
        from telethon.tl.functions.users import GetFullUserRequest
        from telethon.tl.types import InputUserSelf

        full_result = await client(GetFullUserRequest(InputUserSelf()))
        if full_result and hasattr(full_result, 'users') and full_result.users:
            user = full_result.users[0]
            premium_status = getattr(user, 'premium', None)
            print(f"🔍 Método GetFullUserRequest - Premium: {premium_status}")

            if premium_status is True:
                print("✅ PREMIUM DETECTADO - Método: GetFullUserRequest")
                print("-" * 60)
                return True

    except Exception as e:
        print(f"⚠️  GetFullUserRequest falló: {e}")

    # Resultado final
    print("📱 RESULTADO: Cuenta Estándar (no Premium detectado)")
    print("💡 Más información: https://telegram.org/premium")
    print("-" * 60)
    return False

async def sendHelloMessage(client, peerChannel):
    """Sends welcome message with detailed status information"""
    global is_premium_account, max_file_size

    entity = await client.get_entity(peerChannel)

    print("\n" + "🚀 " * 20)
    print("TELEGRAM DOWNLOAD DAEMON - ENHANCED PREMIUM EDITION")
    print("🚀 " * 20 + "\n")

    # Check Premium status
    is_premium_account = await check_premium_status(client)

    # Configure parameters according to account type
    if is_premium_account:
        max_file_size = int(TELEGRAM_DAEMON_PREMIUM_MAX_SIZE)
        account_emoji = "⭐"
        account_type = "Premium"
        features_list = [
            "✅ Files up to 4GB",
            "✅ No speed limits",
            "✅ Optimized downloads",
            "✅ Server priority",
            "✅ Enhanced parallel workers"
        ]
    else:
        max_file_size = 2000
        account_emoji = "📱"
        account_type = "Standard"
        features_list = [
            "⚡ Standard speed",
            "📁 Files up to 2GB",
            "🔄 Full functionality"
        ]

    # Apply configurations
    configure_client_for_premium(is_premium_account)

    # Build detailed welcome message
    hello_msg = f"{'='*50}\n"
    hello_msg += f"🚀 **TELEGRAM DOWNLOAD DAEMON**\n"
    hello_msg += f"📦 **Version {TDD_VERSION}**\n"
    hello_msg += f"{'='*50}\n\n"

    # System information
    hello_msg += f"🔧 **SYSTEM INFORMATION**\n"
    hello_msg += f"├─ 📚 Telethon: `{__version__}`\n"
    hello_msg += f"├─ 🐍 Python Asyncio\n"
    hello_msg += f"├─ 🖥️  CPU Cores: `{multiprocessing.cpu_count()}`\n"
    hello_msg += f"└─ 📅 Started: `{stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}`\n\n"

    # Account status - HIGHLIGHTED
    hello_msg += f"{'─'*50}\n"
    if is_premium_account:
        hello_msg += f"🌟 **PREMIUM ACCOUNT DETECTED** 🌟\n"
    else:
        hello_msg += f"📱 **STANDARD ACCOUNT DETECTED**\n"
    hello_msg += f"{'─'*50}\n\n"

    hello_msg += f"👤 **ACCOUNT STATUS**\n"
    hello_msg += f"├─ {account_emoji} Type: **{account_type}**\n"
    hello_msg += f"├─ 📁 File limit: **{max_file_size:,} MB**\n"
    hello_msg += f"└─ 🔄 Parallel workers: **{worker_count}**\n\n"

    # Available features
    hello_msg += f"✨ **ACTIVE FEATURES**\n"
    for feature in features_list:
        hello_msg += f"{feature}\n"
    hello_msg += "\n"

    # Premium optimizations (if applicable)
    if is_premium_account:
        hello_msg += f"🎯 **PREMIUM OPTIMIZATIONS**\n"
        hello_msg += f"⚡ No FLOOD_WAIT limits\n"
        hello_msg += f"📦 1MB chunks for large files\n"
        hello_msg += f"🚀 3x improved parallelism\n"
        hello_msg += f"💎 Priority on Telegram servers\n\n"

    # Download configuration
    hello_msg += f"⚙️  **CONFIGURATION**\n"
    hello_msg += f"├─ 📂 Destination: `{downloadFolder}`\n"
    hello_msg += f"├─ 🔄 Duplicates: `{duplicates}`\n"
    if TELEGRAM_DAEMON_FILE_FILTER:
        hello_msg += f"├─ 🎯 Filters: `{TELEGRAM_DAEMON_FILE_FILTER}`\n"
    hello_msg += f"└─ 💾 Temporary: `{tempFolder}`\n\n"

    # Available commands
    hello_msg += f"📝 **AVAILABLE COMMANDS**\n"
    hello_msg += f"└─ Type `help` to see all commands\n\n"

    hello_msg += f"{'='*50}\n"
    hello_msg += f"✅ **SYSTEM READY FOR DOWNLOADS**\n"
    hello_msg += f"{'='*50}\n"

    if not is_premium_account:
        hello_msg += f"\n💡 **Tip:** Upgrade to Premium for better performance\n"
        hello_msg += f"📎 https://telegram.org/premium"

    await client.send_message(entity, hello_msg)
    print("✅ Welcome message sent to channel")
    print("\n" + "🎉 " * 20)
    print("DAEMON FULLY INITIALIZED AND READY")
    print("🎉 " * 20 + "\n")

async def log_reply(message, reply):
    """Registra y edita el mensaje con la respuesta"""
    print(reply)
    await message.edit(reply)

def getRandomId(len):
    """Genera un ID aleatorio"""
    chars=string.ascii_lowercase + string.digits
    return  ''.join(random.choice(chars) for x in range(len))

def getFilename(event: events.NewMessage.Event):
    """Extrae el nombre del archivo del evento"""
    mediaFileName = "unknown"

    if hasattr(event.media, 'photo'):
        mediaFileName = str(event.media.photo.id)+".jpeg"
    elif hasattr(event.media, 'document'):
        for attribute in event.media.document.attributes:
            if isinstance(attribute, DocumentAttributeFilename):
              mediaFileName=attribute.file_name
              break
            if isinstance(attribute, DocumentAttributeVideo):
              if event.original_update.message.message != '':
                  mediaFileName = event.original_update.message.message
              else:
                  mediaFileName = str(event.message.media.document.id)
              mediaFileName+=guess_extension(event.message.media.document.mime_type)

    mediaFileName="".join(c for c in mediaFileName if c.isalnum() or c in "()._- ")

    return mediaFileName

def is_file_allowed(filename):
    """Verifica si el archivo pasa los filtros configurados"""
    if not TELEGRAM_DAEMON_FILE_FILTER:
        return True

    allowed_extensions = [ext.strip().lower() for ext in TELEGRAM_DAEMON_FILE_FILTER.split(',')]

    # Usar os.path.splitext para extraer extensión de forma robusta
    _, file_extension = os.path.splitext(filename)
    file_extension = file_extension.lstrip('.').lower() if file_extension else ''

    return file_extension in allowed_extensions

in_progress={}
download_start_times = {}

async def set_progress(filename, message, received, total):
    """Actualiza el progreso de descarga con velocidad (thread-safe)"""
    global lastUpdate
    global updateFrequency

    async with progress_lock:
        if received >= total:
            try:
                in_progress.pop(filename)
                download_start_times.pop(filename, None)
            except Exception:
                pass
            return

        percentage = math.trunc(received / total * 10000) / 100

        # Calcular velocidad de descarga
        current_time = time.time()
        start_time = download_start_times.get(filename, current_time)
        elapsed_time = current_time - start_time

        if elapsed_time > 0:
            speed = received / elapsed_time
            eta_seconds = (total - received) / speed if speed > 0 else 0

            progress_message = f"📥 {percentage:.1f}% ({format_bytes(received)} / {format_bytes(total)})\n"
            progress_message += f"⚡ Speed: {format_speed(speed)}\n"
            progress_message += f"⏱️ ETA: {format_time(eta_seconds)}"

            # Guardar velocidad para estadísticas (con lock)
            if speed > 0:
                async with stats_lock:
                    stats['download_speeds'].append(speed)
        else:
            progress_message = f"{percentage:.1f}% ({format_bytes(received)} / {format_bytes(total)})"

        in_progress[filename] = progress_message

        if (current_time - lastUpdate) > updateFrequency:
            await log_reply(message, progress_message)
            lastUpdate=current_time


with TelegramClient(getSession(), api_id, api_hash,
                    proxy=proxy,
                    connection_retries=5,
                    retry_delay=2,
                    timeout=60,
                    device_model="TDD Premium Enhanced",
                    system_version="2.0",
                    app_version=TDD_VERSION,
                    ).start() as client:

    saveSession(client.session)

    queue = asyncio.Queue()
    peerChannel = PeerChannel(channel_id)

    @client.on(events.NewMessage())
    async def handler(event):

        if event.to_id != peerChannel:
            return

        print(event)

        try:

            if not event.media and event.message:
                command = event.message.message
                command = command.lower()
                output = "Unknown command"

                if command == "help":
                    output = "📚 **AVAILABLE COMMANDS**\n\n"
                    output += "**Information:**\n"
                    output += "├─ `status` - View active downloads and account info\n"
                    output += "├─ `config` - View current configuration\n"
                    output += "├─ `stats` - View session statistics\n"
                    output += "└─ `help` - Show this help\n\n"
                    output += "**Management:**\n"
                    output += "├─ `queue` - View files in queue\n"
                    output += "├─ `list` - List downloaded files\n"
                    output += "├─ `clean` - Clean temporary files\n"
                    output += "├─ `pause` - Pause downloads\n"
                    output += "└─ `resume` - Resume downloads\n\n"
                    output += "**Usage:**\n"
                    output += "└─ Forward any file to the channel to download it\n\n"
                    output += f"💡 Version: {TDD_VERSION}"

                elif command == "config":
                    output = "⚙️  **CURRENT CONFIGURATION**\n\n"
                    output += f"👤 **Account:**\n"
                    output += f"├─ Type: {'Premium ⭐' if is_premium_account else 'Standard 📱'}\n"
                    output += f"├─ File limit: {max_file_size} MB\n"
                    output += f"└─ Workers: {worker_count}\n\n"
                    output += f"📂 **Paths:**\n"
                    output += f"├─ Downloads: `{downloadFolder}`\n"
                    output += f"└─ Temporary: `{tempFolder}`\n\n"
                    output += f"🔧 **Options:**\n"
                    output += f"├─ Duplicates: `{duplicates}`\n"
                    if TELEGRAM_DAEMON_FILE_FILTER:
                        output += f"├─ Filters: `{TELEGRAM_DAEMON_FILE_FILTER}`\n"
                    output += f"└─ Status: {'⏸️ Paused' if download_paused else '▶️ Active'}\n\n"
                    if is_premium_account:
                        output += f"✨ **Premium Optimizations:**\n"
                        output += f"├─ No speed limits\n"
                        output += f"├─ Optimized chunks\n"
                        output += f"└─ Enhanced parallelism"

                elif command == "stats":
                    uptime = datetime.now() - stats['session_start']
                    # Use constant for speed sample count
                    recent_speeds = list(stats['download_speeds'])[-SPEED_SAMPLES_FOR_AVERAGE:]
                    avg_speed = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0

                    output = "📊 **SESSION STATISTICS**\n\n"
                    output += f"⏱️ **Uptime:** {format_time(uptime.total_seconds())}\n"
                    output += f"📅 **Started:** {stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    output += f"📥 **Downloads:**\n"
                    output += f"├─ Total: {stats['total_downloads']}\n"
                    output += f"├─ Successful: {stats['successful_downloads']} ✅\n"
                    output += f"├─ Failed: {stats['failed_downloads']} ❌\n"
                    if stats['total_downloads'] > 0:
                        success_rate = (stats['successful_downloads'] / stats['total_downloads']) * 100
                        output += f"└─ Success rate: {success_rate:.1f}%\n\n"

                    output += f"💾 **Data:**\n"
                    output += f"├─ Total downloaded: {format_bytes(stats['total_bytes'])}\n"
                    if avg_speed > 0:
                        output += f"├─ Average speed: {format_speed(avg_speed)}\n"
                    if stats['largest_file']['name']:
                        output += f"└─ Largest file:\n"
                        output += f"    • {stats['largest_file']['name']}\n"
                        output += f"    • {format_bytes(stats['largest_file']['size'])}\n"

                elif command == "list":
                    # Security: don't use shell=True
                    result = subprocess.run(["ls", "-lh", downloadFolder], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    output = result.stdout.decode('utf-8')
                    if output and output.strip():
                        output = f"📁 **Downloaded files:**\n\n```\n{output}\n```"
                    else:
                        output = "📁 Download folder is empty"

                elif command == "status":
                    try:
                        if in_progress:
                            output = "📥 **ACTIVE DOWNLOADS:**\n\n"
                            for filename, progress in in_progress.items():
                                output += f"📄 **{filename}**\n{progress}\n\n"
                        else:
                            output = "✅ **No active downloads**\n\n"

                        # Account information
                        output += f"{'─'*40}\n"
                        output += f"🏷️ **ACCOUNT INFORMATION**\n\n"
                        output += f"👤 Type: **{'Premium ⭐' if is_premium_account else 'Standard 📱'}**\n"
                        output += f"📁 Limit: **{max_file_size} MB**\n"
                        output += f"🔄 Workers: **{worker_count}**\n"
                        output += f"📊 Status: **{'⏸️ Paused' if download_paused else '▶️ Active'}**\n"

                        if is_premium_account:
                            output += f"\n⚡ **Premium optimizations active**"
                        else:
                            output += f"\n💡 Consider Premium for better performance"

                    except Exception as e:
                        output = f"❌ Error checking status: {str(e)}"

                elif command == "pause":
                    # Use Event for thread-safe synchronization
                    download_pause_event.clear()
                    output = "⏸️ **Downloads paused**\n\n"
                    output += "Current downloads will continue, but new files won't be processed from the queue.\n\n"
                    output += "Type `resume` to continue."

                elif command == "resume":
                    # Use Event for thread-safe synchronization
                    download_pause_event.set()
                    output = "▶️ **Downloads resumed**\n\n"
                    output += "Queue processing has been reactivated."

                elif command == "clean":
                    output = "🧹 **Cleaning temporary files...**\n\n"
                    output += f"📂 Folder: `{tempFolder}`\n\n"

                    # Security: use glob instead of shell=True
                    import os
                    temp_files = glob.glob(os.path.join(tempFolder, f"*.{TELEGRAM_DAEMON_TEMP_SUFFIX}"))
                    removed_count = 0

                    for temp_file in temp_files:
                        try:
                            os.remove(temp_file)
                            removed_count += 1
                        except Exception as e:
                            print(f"Error removing {temp_file}: {e}")

                    if removed_count > 0:
                        output += f"✅ **{removed_count} temporary file(s) removed**"
                    else:
                        output += "ℹ️ **No temporary files to remove**"

                elif command == "queue":
                    try:
                        files_in_queue = []
                        for q in queue.__dict__['_queue']:
                            files_in_queue.append(getFilename(q[0]))

                        if files_in_queue:
                            output = f"📋 **FILES IN QUEUE ({len(files_in_queue)})**\n\n"
                            for i, filename in enumerate(files_in_queue, 1):
                                output += f"{i}. {filename}\n"
                        else:
                            output = "✅ **Queue is empty**\n\n"
                            output += "Forward files to the channel to add them to the queue."
                    except Exception as e:
                        output = f"❌ Error checking queue: {str(e)}"
                else:
                    output = "❓ **Unknown command**\n\n"
                    output += "Type `help` to see available commands."

                await log_reply(event, output)

            if event.media:
                if hasattr(event.media, 'document') or hasattr(event.media,'photo'):
                    filename=getFilename(event)

                    # Check file filters
                    if not is_file_allowed(filename):
                        await event.reply(f"⏭️ **File filtered**\n\n"
                                        f"📄 {filename}\n"
                                        f"🎯 Allowed extensions: `{TELEGRAM_DAEMON_FILE_FILTER}`")
                        return

                    # Check file size
                    if hasattr(event.media, 'document'):
                        file_size_mb = event.media.document.size / (1024 * 1024)

                        if not is_premium_account and file_size_mb > 2000:
                            message = await event.reply(
                                f"❌ **FILE TOO LARGE**\n\n"
                                f"📄 **File:** {filename}\n"
                                f"📦 **Size:** {file_size_mb:.2f} MB\n"
                                f"⚠️  **Current limit:** 2,000 MB\n\n"
                                f"{'─'*40}\n"
                                f"💡 **SOLUTION**\n"
                                f"Upgrade to Telegram Premium for:\n"
                                f"• Files up to 4GB\n"
                                f"• No speed limits\n"
                                f"• Download priority\n\n"
                                f"📎 https://telegram.org/premium"
                            )
                            return
                        elif file_size_mb > max_file_size:
                            message = await event.reply(
                                f"❌ **File exceeds configured limit**\n\n"
                                f"📄 **File:** {filename}\n"
                                f"📦 **Size:** {file_size_mb:.2f} MB\n"
                                f"⚠️  **Limit:** {max_file_size} MB"
                            )
                            return

                        # Valid file
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or
                             path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply(f"⏭️ **{filename}** already exists. Ignoring.")
                        else:
                            queue_size = queue.qsize()

                            message_text = f"✅ **Added to queue**\n\n"
                            message_text += f"📄 **File:** {filename}\n"
                            message_text += f"📦 **Size:** {format_bytes(event.media.document.size)}\n"
                            message_text += f"📋 **Queue position:** {queue_size + 1}\n"
                            if is_premium_account and file_size_mb > 2000:
                                message_text += f"\n⭐ **Premium:** Large file detected"

                            message=await event.reply(message_text)
                            await queue.put([event, message])
                    else:
                        # Photos
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or
                             path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply(f"⏭️ **{filename}** already exists. Ignoring.")
                        else:
                            message=await event.reply(f"✅ **{filename}** added to queue")
                            await queue.put([event, message])
                else:
                    message=await event.reply("❌ **Not downloadable**\n\nSend the file as a document.")

        except Exception as e:
                print('Events handler error: ', e)

    async def worker():
        """Worker mejorado con reintentos y mejor manejo de errores (thread-safe)"""
        while True:
            try:
                # Esperar si está pausado (thread-safe usando Event)
                await download_pause_event.wait()

                element = await queue.get()
                event=element[0]
                message=element[1]

                filename=getFilename(event)
                fileName, fileExtension = os.path.splitext(filename)
                tempfilename=fileName+"-"+getRandomId(8)+fileExtension

                if path.exists("{0}/{1}.{2}".format(tempFolder,tempfilename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or path.exists("{0}/{1}".format(downloadFolder,filename)):
                    if duplicates == "rename":
                       filename=tempfilename


                if hasattr(event.media, 'photo'):
                   size = 0
                else:
                   size=event.media.document.size

                size_mb = size / (1024 * 1024)

                # Increment total downloads counter (thread-safe)
                async with stats_lock:
                    stats['total_downloads'] += 1

                # Improved download start message
                download_info = f"🚀 **STARTING DOWNLOAD**\n\n"
                download_info += f"📄 **File:** {filename}\n"
                download_info += f"📦 **Size:** {format_bytes(size)}"

                if size_mb > 0:
                    download_info += f" ({size_mb:.2f} MB)"

                download_info += f"\n🔄 **Mode:** {'Premium ⭐' if is_premium_account else 'Standard 📱'}\n"

                if is_premium_account and size_mb > 2000:
                    download_info += f"\n💎 **Premium large file detected**"

                await log_reply(message, download_info)

                # Registrar tiempo de inicio
                download_start_times[filename] = time.time()

                download_callback = lambda received, total: set_progress(filename, message, received, total)

                # Intentar descarga con reintentos (usa constantes MAX_RETRIES y RETRY_DELAY_BASE)
                retry_count = 0
                download_success = False

                while retry_count < MAX_RETRIES and not download_success:
                    try:
                        if is_premium_account and size_mb > 50:
                            # Descarga optimizada Premium
                            print(f"🚀 Descarga Premium optimizada: {filename}")
                            await client.download_media(
                                event.message,
                                "{0}/{1}.{2}".format(tempFolder, filename, TELEGRAM_DAEMON_TEMP_SUFFIX),
                                progress_callback=download_callback,
                            )
                        else:
                            # Descarga estándar
                            await client.download_media(
                                event.message,
                                "{0}/{1}.{2}".format(tempFolder, filename, TELEGRAM_DAEMON_TEMP_SUFFIX),
                                progress_callback=download_callback
                            )

                        download_success = True

                    except Exception as download_error:
                        retry_count += 1
                        error_msg = str(download_error)

                        if retry_count < MAX_RETRIES:
                            # Linear backoff: wait increases linearly (5s, 10s, 15s)
                            wait_time = retry_count * RETRY_DELAY_BASE
                            await log_reply(message,
                                f"⚠️ **Retry {retry_count}/{MAX_RETRIES}**\n\n"
                                f"Error: {error_msg}\n"
                                f"Waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            raise download_error

                # Download completed successfully
                set_progress(filename, message, 100, 100)
                move("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX),
                     "{0}/{1}".format(downloadFolder,filename))

                # Update statistics (thread-safe)
                async with stats_lock:
                    stats['successful_downloads'] += 1
                    stats['total_bytes'] += size

                    if size > stats['largest_file']['size']:
                        stats['largest_file'] = {'name': filename, 'size': size}

                # Calculate time and speed
                download_time = time.time() - download_start_times.get(filename, time.time())
                avg_speed = size / download_time if download_time > 0 else 0

                # Improved completion message
                completion_msg = f"✅ **DOWNLOAD COMPLETED**\n\n"
                completion_msg += f"📄 **File:** {filename}\n"
                completion_msg += f"📦 **Size:** {format_bytes(size)}"

                if size_mb > 1:
                    completion_msg += f" ({size_mb:.2f} MB)"

                completion_msg += f"\n⏱️ **Time:** {format_time(download_time)}\n"

                if avg_speed > 0:
                    completion_msg += f"⚡ **Average speed:** {format_speed(avg_speed)}\n"

                completion_msg += f"📁 **Location:** `{downloadFolder}`\n\n"
                completion_msg += f"{'─'*40}\n"
                completion_msg += f"✨ Download #{stats['successful_downloads']} of this session"

                await log_reply(message, completion_msg)

                queue.task_done()

            except Exception as e:
                # Update failure statistics (thread-safe)
                async with stats_lock:
                    stats['failed_downloads'] += 1

                try:
                    error_msg = f"❌ **DOWNLOAD ERROR**\n\n"
                    error_msg += f"📄 **File:** {filename}\n"
                    error_msg += f"🚨 **Error:** {str(e)}\n"
                    error_msg += f"🔄 **Retries exhausted:** {MAX_RETRIES}\n\n"

                    # Specific suggestions
                    error_lower = str(e).lower()
                    if "file too large" in error_lower or "flood" in error_lower:
                        if not is_premium_account:
                            error_msg += f"💡 **Suggested solution:**\n"
                            error_msg += f"Upgrade to Premium for:\n"
                            error_msg += f"• Files up to 4GB\n"
                            error_msg += f"• No speed limits\n"
                            error_msg += f"• Enhanced automatic retries\n\n"
                            error_msg += f"📎 https://telegram.org/premium"
                        else:
                            error_msg += f"💡 File will be skipped."
                    elif "timeout" in error_lower:
                        error_msg += f"💡 **Network problem**\n"
                        error_msg += f"Check your internet connection."

                    await log_reply(message, error_msg)
                except Exception as log_exc:
                    print(f'Error logging message: {log_exc}')

                print(f'Queue worker error: {e}')
                queue.task_done()

    async def start():
        """Inicio del daemon"""
        global stats_lock, progress_lock, download_pause_event

        # Inicializar locks y events para sincronización thread-safe
        stats_lock = asyncio.Lock()
        progress_lock = asyncio.Lock()
        download_pause_event = asyncio.Event()
        download_pause_event.set()  # Inicialmente no pausado

        tasks = []
        loop = asyncio.get_event_loop()

        for i in range(worker_count):
            task = loop.create_task(worker())
            tasks.append(task)

        await sendHelloMessage(client, peerChannel)
        await client.run_until_disconnected()

        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    client.loop.run_until_complete(start())
