#!/usr/bin/env python3
# Telegram Download Daemon - Enhanced Premium Edition
# Original Author: Alfonso E.M. <alfonso@el-magnifico.org>
# Enhanced with Premium features and improved UX
# Version: 2.0-Premium-Enhanced (FIXED)
# FIXES: Global variable handling, race conditions, and error handling

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
from collections import defaultdict

from sessionManager import getSession, saveSession

from telethon import TelegramClient, events, __version__
from telethon.tl.types import PeerChannel, DocumentAttributeFilename, DocumentAttributeVideo
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s]%(name)s:%(message)s',
                    level=logging.WARNING)

import multiprocessing
import argparse
import asyncio


TDD_VERSION="2.0-Premium-Enhanced-FIXED"

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
TELEGRAM_DAEMON_FILE_FILTER=getenv("TELEGRAM_DAEMON_FILE_FILTER", "")

# Variables globales - INICIALIZADAS CORRECTAMENTE
is_premium_account = False
max_file_size = 2000  # MB por defecto
download_paused = False
lastUpdate = time.time()  # FIXED: Inicializar con timestamp actual

# Estadísticas globales
stats = {
    'total_downloads': 0,
    'successful_downloads': 0,
    'failed_downloads': 0,
    'total_bytes': 0,
    'session_start': datetime.now(),
    'largest_file': {'name': '', 'size': 0},
    'download_speeds': []
}

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
    'Destination path for downloaded files (default is /telegram-downloads).'
)
parser.add_argument(
    "--temp",
    type=str,
    default=TELEGRAM_DAEMON_TEMP,
    help=
    'Destination path for temporary files (default is using the same downloaded files directory).'
)
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

if not tempFolder:
    tempFolder = downloadFolder

# Edit these lines:
proxy = None

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
        print(f"   📦 Archivos hasta {TELEGRAM_DAEMON_PREMIUM_MAX_SIZE} MB (vs 2000 MB estándar)")
        print(f"   🎯 Chunks optimizados: 1MB para archivos grandes")
        print(f"   🚀 Paralelismo mejorado para múltiples archivos")
        print(f"   💎 Prioridad Premium en servidores de Telegram")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("📱 MODO ESTÁNDAR ACTIVADO")
        print("="*60)
        print(f"⚙️  Configuración aplicada:")
        print(f"   📦 Archivos hasta 2000 MB")
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
    """Envía mensaje de bienvenida con información detallada del estado"""
    global is_premium_account, max_file_size

    entity = await client.get_entity(peerChannel)

    print("\n" + "🚀 " * 20)
    print("TELEGRAM DOWNLOAD DAEMON - ENHANCED PREMIUM EDITION")
    print("🚀 " * 20 + "\n")

    # Verificar estado Premium
    is_premium_account = await check_premium_status(client)

    # Configurar parámetros según tipo de cuenta - FIXED
    if is_premium_account:
        max_file_size = int(TELEGRAM_DAEMON_PREMIUM_MAX_SIZE)
        account_emoji = "⭐"
        account_type = "Premium"
        features_list = [
            "✅ Archivos hasta 4GB",
            "✅ Sin límites de velocidad",
            "✅ Descarga optimizada",
            "✅ Prioridad en servidores",
            "✅ Workers paralelos mejorados"
        ]
    else:
        max_file_size = 2000
        account_emoji = "📱"
        account_type = "Estándar"
        features_list = [
            "⚡ Velocidad estándar",
            "📁 Archivos hasta 2GB",
            "🔄 Funcionalidad completa"
        ]

    # Aplicar configuraciones
    configure_client_for_premium(is_premium_account)

    # Construir mensaje de bienvenida detallado
    hello_msg = f"{'='*50}\n"
    hello_msg += f"🚀 **TELEGRAM DOWNLOAD DAEMON**\n"
    hello_msg += f"📦 **Versión {TDD_VERSION}**\n"
    hello_msg += f"{'='*50}\n\n"

    # Información del sistema
    hello_msg += f"🔧 **INFORMACIÓN DEL SISTEMA**\n"
    hello_msg += f"├─ 📚 Telethon: `{__version__}`\n"
    hello_msg += f"├─ 🐍 Python Asyncio\n"
    hello_msg += f"├─ 🖥️  CPU Cores: `{multiprocessing.cpu_count()}`\n"
    hello_msg += f"└─ 📅 Inicio: `{stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}`\n\n"

    # Estado de la cuenta - DESTACADO
    hello_msg += f"{'─'*50}\n"
    if is_premium_account:
        hello_msg += f"🌟 **CUENTA PREMIUM DETECTADA** 🌟\n"
    else:
        hello_msg += f"📱 **CUENTA ESTÁNDAR DETECTADA**\n"
    hello_msg += f"{'─'*50}\n\n"

    hello_msg += f"👤 **ESTADO DE CUENTA**\n"
    hello_msg += f"├─ {account_emoji} Tipo: **{account_type}**\n"
    hello_msg += f"├─ 📁 Límite de archivo: **{max_file_size:,} MB**\n"
    hello_msg += f"└─ 🔄 Workers paralelos: **{worker_count}**\n\n"

    # Características disponibles
    hello_msg += f"✨ **CARACTERÍSTICAS ACTIVAS**\n"
    for feature in features_list:
        hello_msg += f"{feature}\n"
    hello_msg += "\n"

    # Optimizaciones Premium (si aplica)
    if is_premium_account:
        hello_msg += f"🎯 **OPTIMIZACIONES PREMIUM**\n"
        hello_msg += f"⚡ Sin límites FLOOD_WAIT\n"
        hello_msg += f"📦 Chunks de 1MB para grandes archivos\n"
        hello_msg += f"🚀 Paralelismo x3 mejorado\n"
        hello_msg += f"💎 Prioridad en servidores Telegram\n\n"

    # Configuración de descarga
    hello_msg += f"⚙️  **CONFIGURACIÓN**\n"
    hello_msg += f"├─ 📂 Destino: `{downloadFolder}`\n"
    hello_msg += f"├─ 🔄 Duplicados: `{duplicates}`\n"
    if TELEGRAM_DAEMON_FILE_FILTER:
        hello_msg += f"├─ 🎯 Filtros: `{TELEGRAM_DAEMON_FILE_FILTER}`\n"
    hello_msg += f"└─ 💾 Temporal: `{tempFolder}`\n\n"

    # Comandos disponibles
    hello_msg += f"📝 **COMANDOS DISPONIBLES**\n"
    hello_msg += f"└─ Escribe `help` para ver todos los comandos\n\n"

    hello_msg += f"{'='*50}\n"
    hello_msg += f"✅ **SISTEMA LISTO PARA DESCARGAS**\n"
    hello_msg += f"{'='*50}\n"

    if not is_premium_account:
        hello_msg += f"\n💡 **Tip:** Actualiza a Premium para mejor rendimiento\n"
        hello_msg += f"📎 https://telegram.org/premium"

    await client.send_message(entity, hello_msg)
    print("✅ Mensaje de bienvenida enviado al canal")
    print("\n" + "🎉 " * 20)
    print("DAEMON COMPLETAMENTE INICIALIZADO Y LISTO")
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
    file_extension = filename.split('.')[-1].lower() if '.' in filename else ''

    return file_extension in allowed_extensions

in_progress={}
download_start_times = {}

async def set_progress(filename, message, received, total):
    """Actualiza el progreso de descarga con velocidad"""
    global lastUpdate

    if received >= total:
        try:
            in_progress.pop(filename)
            download_start_times.pop(filename, None)
        except: pass
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
        progress_message += f"⚡ Velocidad: {format_speed(speed)}\n"
        progress_message += f"⏱️ ETA: {format_time(eta_seconds)}"

        # Guardar velocidad para estadísticas
        if speed > 0:
            stats['download_speeds'].append(speed)
    else:
        progress_message = f"{percentage:.1f}% ({format_bytes(received)} / {format_bytes(total)})"

    in_progress[filename] = progress_message

    # FIXED: Usar time.time() directamente para evitar race conditions
    if (current_time - lastUpdate) > updateFrequency:
        await log_reply(message, progress_message)
        lastUpdate = current_time


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
        global download_paused  # FIXED: Declarar aquí para evitar UnboundLocalError

        if event.to_id != peerChannel:
            return

        print(event)

        try:

            if not event.media and event.message:
                command = event.message.message
                command = command.lower()
                output = "Unknown command"

                if command == "help":
                    output = "📚 **COMANDOS DISPONIBLES**\n\n"
                    output += "**Información:**\n"
                    output += "├─ `status` - Ver descargas activas e info de cuenta\n"
                    output += "├─ `config` - Ver configuración actual\n"
                    output += "├─ `stats` - Ver estadísticas de sesión\n"
                    output += "└─ `help` - Mostrar esta ayuda\n\n"
                    output += "**Gestión:**\n"
                    output += "├─ `queue` - Ver archivos en cola\n"
                    output += "├─ `list` - Listar archivos descargados\n"
                    output += "├─ `clean` - Limpiar archivos temporales\n"
                    output += "├─ `pause` - Pausar descargas\n"
                    output += "└─ `resume` - Reanudar descargas\n\n"
                    output += "**Uso:**\n"
                    output += "└─ Reenvía cualquier archivo al canal para descargarlo\n\n"
                    output += f"💡 Versión: {TDD_VERSION}"

                elif command == "config":
                    output = "⚙️  **CONFIGURACIÓN ACTUAL**\n\n"
                    output += f"👤 **Cuenta:**\n"
                    output += f"├─ Tipo: {'Premium ⭐' if is_premium_account else 'Estándar 📱'}\n"
                    output += f"├─ Límite archivo: {max_file_size} MB\n"
                    output += f"└─ Workers: {worker_count}\n\n"
                    output += f"📂 **Rutas:**\n"
                    output += f"├─ Descargas: `{downloadFolder}`\n"
                    output += f"└─ Temporal: `{tempFolder}`\n\n"
                    output += f"🔧 **Opciones:**\n"
                    output += f"├─ Duplicados: `{duplicates}`\n"
                    if TELEGRAM_DAEMON_FILE_FILTER:
                        output += f"├─ Filtros: `{TELEGRAM_DAEMON_FILE_FILTER}`\n"
                    output += f"└─ Estado: {'⏸️ Pausado' if download_paused else '▶️ Activo'}\n\n"
                    if is_premium_account:
                        output += f"✨ **Optimizaciones Premium:**\n"
                        output += f"├─ Sin límites de velocidad\n"
                        output += f"├─ Chunks optimizados\n"
                        output += f"└─ Paralelismo mejorado"

                elif command == "stats":
                    uptime = datetime.now() - stats['session_start']
                    avg_speed = sum(stats['download_speeds'][-10:]) / len(stats['download_speeds'][-10:]) if stats['download_speeds'] else 0

                    output = "📊 **ESTADÍSTICAS DE SESIÓN**\n\n"
                    output += f"⏱️ **Tiempo activo:** {format_time(uptime.total_seconds())}\n"
                    output += f"📅 **Inicio:** {stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    output += f"📥 **Descargas:**\n"
                    output += f"├─ Total: {stats['total_downloads']}\n"
                    output += f"├─ Exitosas: {stats['successful_downloads']} ✅\n"
                    output += f"├─ Fallidas: {stats['failed_downloads']} ❌\n"
                    if stats['total_downloads'] > 0:
                        success_rate = (stats['successful_downloads'] / stats['total_downloads']) * 100
                        output += f"└─ Tasa éxito: {success_rate:.1f}%\n\n"

                    output += f"💾 **Datos:**\n"
                    output += f"├─ Total descargado: {format_bytes(stats['total_bytes'])}\n"
                    if avg_speed > 0:
                        output += f"├─ Velocidad promedio: {format_speed(avg_speed)}\n"
                    if stats['largest_file']['name']:
                        output += f"└─ Archivo más grande:\n"
                        output += f"    • {stats['largest_file']['name']}\n"
                        output += f"    • {format_bytes(stats['largest_file']['size'])}\n"

                elif command == "list":
                    output = subprocess.run(["ls -lh "+downloadFolder], shell=True, stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode('utf-8')
                    if output:
                        output = f"📁 **Archivos descargados:**\n\n```\n{output}\n```"
                    else:
                        output = "📁 La carpeta de descargas está vacía"

                elif command == "status":
                    try:
                        if in_progress:
                            output = "📥 **DESCARGAS ACTIVAS:**\n\n"
                            for filename, progress in in_progress.items():
                                output += f"📄 **{filename}**\n{progress}\n\n"
                        else:
                            output = "✅ **Sin descargas activas**\n\n"

                        # Información de cuenta
                        output += f"{'─'*40}\n"
                        output += f"🏷️ **INFORMACIÓN DE CUENTA**\n\n"
                        output += f"👤 Tipo: **{'Premium ⭐' if is_premium_account else 'Estándar 📱'}**\n"
                        output += f"📁 Límite: **{max_file_size} MB**\n"
                        output += f"🔄 Workers: **{worker_count}**\n"
                        output += f"📊 Estado: **{'⏸️ Pausado' if download_paused else '▶️ Activo'}**\n"

                        if is_premium_account:
                            output += f"\n⚡ **Optimizaciones Premium activas**"
                        else:
                            output += f"\n💡 Considera Premium para mejor rendimiento"

                    except Exception as e:
                        output = f"❌ Error al verificar estado: {str(e)}"

                elif command == "pause":
                    download_paused = True  # FIXED: Ya está declarado como global arriba
                    output = "⏸️ **Descargas pausadas**\n\n"
                    output += "Las descargas actuales continuarán, pero no se procesarán nuevos archivos de la cola.\n\n"
                    output += "Escribe `resume` para reanudar."

                elif command == "resume":
                    download_paused = False  # FIXED: Ya está declarado como global arriba
                    output = "▶️ **Descargas reanudadas**\n\n"
                    output += "El procesamiento de la cola se ha reactivado."

                elif command == "clean":
                    output = "🧹 **Limpiando archivos temporales...**\n\n"
                    output += f"📂 Carpeta: `{tempFolder}`\n\n"
                    result = subprocess.run(
                        "rm " + tempFolder + "/*." + TELEGRAM_DAEMON_TEMP_SUFFIX,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    ).stdout.decode("utf-8")
                    output += f"```\n{result if result else 'Sin archivos temporales para eliminar'}\n```\n"
                    output += "✅ Limpieza completada"

                elif command == "queue":
                    try:
                        files_in_queue = []
                        for q in queue.__dict__['_queue']:
                            files_in_queue.append(getFilename(q[0]))

                        if files_in_queue:
                            output = f"📋 **ARCHIVOS EN COLA ({len(files_in_queue)})**\n\n"
                            for i, filename in enumerate(files_in_queue, 1):
                                output += f"{i}. {filename}\n"
                        else:
                            output = "✅ **La cola está vacía**\n\n"
                            output += "Reenvía archivos al canal para añadirlos a la cola."
                    except Exception as e:
                        output = f"❌ Error al verificar cola: {str(e)}"
                else:
                    output = "❓ **Comando no reconocido**\n\n"
                    output += "Escribe `help` para ver los comandos disponibles."

                await log_reply(event, output)

            if event.media:
                if hasattr(event.media, 'document') or hasattr(event.media,'photo'):
                    # FIXED: Envolver getFilename en try-except
                    try:
                        filename = getFilename(event)
                    except Exception as e:
                        await event.reply(f"❌ **Error al procesar archivo**\n\nNo se pudo extraer el nombre del archivo: {str(e)}")
                        return

                    # Verificar filtros de archivo
                    if not is_file_allowed(filename):
                        await event.reply(f"⏭️ **Archivo filtrado**\n\n"
                                        f"📄 {filename}\n"
                                        f"🎯 Extensiones permitidas: `{TELEGRAM_DAEMON_FILE_FILTER}`")
                        return

                    # Verificar tamaño del archivo
                    if hasattr(event.media, 'document'):
                        file_size_mb = event.media.document.size / (1024 * 1024)

                        if not is_premium_account and file_size_mb > 2000:
                            message = await event.reply(
                                f"❌ **ARCHIVO DEMASIADO GRANDE**\n\n"
                                f"📄 **Archivo:** {filename}\n"
                                f"📦 **Tamaño:** {file_size_mb:.2f} MB\n"
                                f"⚠️  **Límite actual:** 2,000 MB\n\n"
                                f"{'─'*40}\n"
                                f"💡 **SOLUCIÓN**\n"
                                f"Actualiza a Telegram Premium para:\n"
                                f"• Archivos hasta 4GB\n"
                                f"• Velocidad sin límites\n"
                                f"• Prioridad en descargas\n\n"
                                f"📎 https://telegram.org/premium"
                            )
                            return
                        elif file_size_mb > max_file_size:
                            message = await event.reply(
                                f"❌ **Archivo excede límite configurado**\n\n"
                                f"📄 **Archivo:** {filename}\n"
                                f"📦 **Tamaño:** {file_size_mb:.2f} MB\n"
                                f"⚠️  **Límite:** {max_file_size} MB"
                            )
                            return

                        # Archivo válido
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or
                             path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply(f"⏭️ **{filename}** ya existe. Ignorando.")
                        else:
                            stats['total_downloads'] += 1
                            queue_size = queue.qsize()

                            message_text = f"✅ **Añadido a la cola**\n\n"
                            message_text += f"📄 **Archivo:** {filename}\n"
                            message_text += f"📦 **Tamaño:** {format_bytes(event.media.document.size)}\n"
                            message_text += f"📋 **Posición en cola:** {queue_size + 1}\n"
                            if is_premium_account and file_size_mb > 2000:
                                message_text += f"\n⭐ **Premium:** Archivo grande detectado"

                            message=await event.reply(message_text)
                            await queue.put([event, message])
                    else:
                        # Fotos
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or
                             path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply(f"⏭️ **{filename}** ya existe. Ignorando.")
                        else:
                            stats['total_downloads'] += 1
                            message=await event.reply(f"✅ **{filename}** añadido a la cola")
                            await queue.put([event, message])
                else:
                    message=await event.reply("❌ **No descargable**\n\nEnvía el archivo como documento.")

        except Exception as e:
                print('Events handler error: ', e)

    async def worker():
        """Worker mejorado con reintentos y mejor manejo de errores"""
        while True:
            try:
                # Verificar si está pausado
                while download_paused:
                    await asyncio.sleep(5)

                element = await queue.get()
                event=element[0]
                message=element[1]

                # FIXED: Envolver getFilename en try-except
                try:
                    filename = getFilename(event)
                except Exception as e:
                    await log_reply(message, f"❌ **Error al procesar archivo**\n\n{str(e)}")
                    queue.task_done()
                    continue

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

                # Mensaje de inicio de descarga mejorado
                download_info = f"🚀 **INICIANDO DESCARGA**\n\n"
                download_info += f"📄 **Archivo:** {filename}\n"
                download_info += f"📦 **Tamaño:** {format_bytes(size)}"

                if size_mb > 0:
                    download_info += f" ({size_mb:.2f} MB)"

                download_info += f"\n🔄 **Modo:** {'Premium ⭐' if is_premium_account else 'Estándar 📱'}\n"

                if is_premium_account and size_mb > 2000:
                    download_info += f"\n💎 **Archivo grande Premium detectado**"

                await log_reply(message, download_info)

                # Registrar tiempo de inicio
                download_start_times[filename] = time.time()

                download_callback = lambda received, total: set_progress(filename, message, received, total)

                # Intentar descarga con reintentos
                max_retries = 3
                retry_count = 0
                download_success = False

                while retry_count < max_retries and not download_success:
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

                        if retry_count < max_retries:
                            wait_time = retry_count * 5
                            await log_reply(message,
                                f"⚠️ **Reintento {retry_count}/{max_retries}**\n\n"
                                f"Error: {error_msg}\n"
                                f"Esperando {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            raise download_error

                # Descarga completada exitosamente
                set_progress(filename, message, 100, 100)
                move("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX),
                     "{0}/{1}".format(downloadFolder,filename))

                # Actualizar estadísticas
                stats['successful_downloads'] += 1
                stats['total_bytes'] += size

                if size > stats['largest_file']['size']:
                    stats['largest_file'] = {'name': filename, 'size': size}

                # Calcular tiempo y velocidad
                download_time = time.time() - download_start_times.get(filename, time.time())
                avg_speed = size / download_time if download_time > 0 else 0

                # Mensaje de finalización mejorado
                completion_msg = f"✅ **DESCARGA COMPLETADA**\n\n"
                completion_msg += f"📄 **Archivo:** {filename}\n"
                completion_msg += f"📦 **Tamaño:** {format_bytes(size)}"

                if size_mb > 1:
                    completion_msg += f" ({size_mb:.2f} MB)"

                completion_msg += f"\n⏱️ **Tiempo:** {format_time(download_time)}\n"

                if avg_speed > 0:
                    completion_msg += f"⚡ **Velocidad promedio:** {format_speed(avg_speed)}\n"

                completion_msg += f"📁 **Ubicación:** `{downloadFolder}`\n\n"
                completion_msg += f"{'─'*40}\n"
                completion_msg += f"✨ Descarga #{stats['successful_downloads']} de esta sesión"

                await log_reply(message, completion_msg)

                queue.task_done()

            except Exception as e:
                # FIXED: Mejor manejo de excepciones
                stats['failed_downloads'] += 1

                try:
                    error_msg = f"❌ **ERROR EN DESCARGA**\n\n"
                    
                    # Usar 'filename' solo si existe
                    try:
                        error_msg += f"📄 **Archivo:** {filename}\n"
                    except NameError:
                        error_msg += f"📄 **Archivo:** [No determinado]\n"
                    
                    error_msg += f"🚨 **Error:** {str(e)}\n"
                    error_msg += f"🔄 **Reintentos agotados:** {max_retries}\n\n"

                    # Sugerencias específicas
                    error_lower = str(e).lower()
                    if "file too large" in error_lower or "flood" in error_lower:
                        if not is_premium_account:
                            error_msg += f"💡 **Solución sugerida:**\n"
                            error_msg += f"Actualiza a Premium para:\n"
                            error_msg += f"• Archivos hasta 4GB\n"
                            error_msg += f"• Sin límites de velocidad\n"
                            error_msg += f"• Reintentos automáticos mejorados\n\n"
                            error_msg += f"📎 https://telegram.org/premium"
                        else:
                            error_msg += f"💡 El archivo será omitido."
                    elif "timeout" in error_lower:
                        error_msg += f"💡 **Problema de red**\n"
                        error_msg += f"Verifica tu conexión a internet."

                    await log_reply(message, error_msg)
                except:
                    pass

                print(f'Queue worker error: {e}')
                queue.task_done()

    async def start():
        """Inicio del daemon"""
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
from collections import defaultdict

from sessionManager import getSession, saveSession

from telethon import TelegramClient, events, __version__
from telethon.tl.types import PeerChannel, DocumentAttributeFilename, DocumentAttributeVideo
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s]%(name)s:%(message)s',
                    level=logging.WARNING)

import multiprocessing
import argparse
import asyncio


TDD_VERSION="2.0-Premium-Enhanced"  # Nueva versión con mejoras significativas

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
download_paused = False

# Estadísticas globales
stats = {
    'total_downloads': 0,
    'successful_downloads': 0,
    'failed_downloads': 0,
    'total_bytes': 0,
    'session_start': datetime.now(),
    'largest_file': {'name': '', 'size': 0},
    'download_speeds': []
}

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
    """Envía mensaje de bienvenida con información detallada del estado"""
    global is_premium_account, max_file_size

    entity = await client.get_entity(peerChannel)

    print("\n" + "🚀 " * 20)
    print("TELEGRAM DOWNLOAD DAEMON - ENHANCED PREMIUM EDITION")
    print("🚀 " * 20 + "\n")

    # Verificar estado Premium
    is_premium_account = await check_premium_status(client)

    # Configurar parámetros según tipo de cuenta
    if is_premium_account:
        max_file_size = int(TELEGRAM_DAEMON_PREMIUM_MAX_SIZE)
        account_emoji = "⭐"
        account_type = "Premium"
        features_list = [
            "✅ Archivos hasta 4GB",
            "✅ Sin límites de velocidad",
            "✅ Descarga optimizada",
            "✅ Prioridad en servidores",
            "✅ Workers paralelos mejorados"
        ]
    else:
        max_file_size = 2000
        account_emoji = "📱"
        account_type = "Estándar"
        features_list = [
            "⚡ Velocidad estándar",
            "📁 Archivos hasta 2GB",
            "🔄 Funcionalidad completa"
        ]

    # Aplicar configuraciones
    configure_client_for_premium(is_premium_account)

    # Construir mensaje de bienvenida detallado
    hello_msg = f"{'='*50}\n"
    hello_msg += f"🚀 **TELEGRAM DOWNLOAD DAEMON**\n"
    hello_msg += f"📦 **Versión {TDD_VERSION}**\n"
    hello_msg += f"{'='*50}\n\n"

    # Información del sistema
    hello_msg += f"🔧 **INFORMACIÓN DEL SISTEMA**\n"
    hello_msg += f"├─ 📚 Telethon: `{__version__}`\n"
    hello_msg += f"├─ 🐍 Python Asyncio\n"
    hello_msg += f"├─ 🖥️  CPU Cores: `{multiprocessing.cpu_count()}`\n"
    hello_msg += f"└─ 📅 Inicio: `{stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}`\n\n"

    # Estado de la cuenta - DESTACADO
    hello_msg += f"{'─'*50}\n"
    if is_premium_account:
        hello_msg += f"🌟 **CUENTA PREMIUM DETECTADA** 🌟\n"
    else:
        hello_msg += f"📱 **CUENTA ESTÁNDAR DETECTADA**\n"
    hello_msg += f"{'─'*50}\n\n"

    hello_msg += f"👤 **ESTADO DE CUENTA**\n"
    hello_msg += f"├─ {account_emoji} Tipo: **{account_type}**\n"
    hello_msg += f"├─ 📁 Límite de archivo: **{max_file_size:,} MB**\n"
    hello_msg += f"└─ 🔄 Workers paralelos: **{worker_count}**\n\n"

    # Características disponibles
    hello_msg += f"✨ **CARACTERÍSTICAS ACTIVAS**\n"
    for feature in features_list:
        hello_msg += f"{feature}\n"
    hello_msg += "\n"

    # Optimizaciones Premium (si aplica)
    if is_premium_account:
        hello_msg += f"🎯 **OPTIMIZACIONES PREMIUM**\n"
        hello_msg += f"⚡ Sin límites FLOOD_WAIT\n"
        hello_msg += f"📦 Chunks de 1MB para grandes archivos\n"
        hello_msg += f"🚀 Paralelismo x3 mejorado\n"
        hello_msg += f"💎 Prioridad en servidores Telegram\n\n"

    # Configuración de descarga
    hello_msg += f"⚙️  **CONFIGURACIÓN**\n"
    hello_msg += f"├─ 📂 Destino: `{downloadFolder}`\n"
    hello_msg += f"├─ 🔄 Duplicados: `{duplicates}`\n"
    if TELEGRAM_DAEMON_FILE_FILTER:
        hello_msg += f"├─ 🎯 Filtros: `{TELEGRAM_DAEMON_FILE_FILTER}`\n"
    hello_msg += f"└─ 💾 Temporal: `{tempFolder}`\n\n"

    # Comandos disponibles
    hello_msg += f"📝 **COMANDOS DISPONIBLES**\n"
    hello_msg += f"└─ Escribe `help` para ver todos los comandos\n\n"

    hello_msg += f"{'='*50}\n"
    hello_msg += f"✅ **SISTEMA LISTO PARA DESCARGAS**\n"
    hello_msg += f"{'='*50}\n"

    if not is_premium_account:
        hello_msg += f"\n💡 **Tip:** Actualiza a Premium para mejor rendimiento\n"
        hello_msg += f"📎 https://telegram.org/premium"

    await client.send_message(entity, hello_msg)
    print("✅ Mensaje de bienvenida enviado al canal")
    print("\n" + "🎉 " * 20)
    print("DAEMON COMPLETAMENTE INICIALIZADO Y LISTO")
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
    file_extension = filename.split('.')[-1].lower() if '.' in filename else ''

    return file_extension in allowed_extensions

in_progress={}
download_start_times = {}

async def set_progress(filename, message, received, total):
    """Actualiza el progreso de descarga con velocidad"""
    global lastUpdate
    global updateFrequency

    if received >= total:
        try:
            in_progress.pop(filename)
            download_start_times.pop(filename, None)
        except: pass
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
        progress_message += f"⚡ Velocidad: {format_speed(speed)}\n"
        progress_message += f"⏱️ ETA: {format_time(eta_seconds)}"

        # Guardar velocidad para estadísticas
        if speed > 0:
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
                    output = "📚 **COMANDOS DISPONIBLES**\n\n"
                    output += "**Información:**\n"
                    output += "├─ `status` - Ver descargas activas e info de cuenta\n"
                    output += "├─ `config` - Ver configuración actual\n"
                    output += "├─ `stats` - Ver estadísticas de sesión\n"
                    output += "└─ `help` - Mostrar esta ayuda\n\n"
                    output += "**Gestión:**\n"
                    output += "├─ `queue` - Ver archivos en cola\n"
                    output += "├─ `list` - Listar archivos descargados\n"
                    output += "├─ `clean` - Limpiar archivos temporales\n"
                    output += "├─ `pause` - Pausar descargas\n"
                    output += "└─ `resume` - Reanudar descargas\n\n"
                    output += "**Uso:**\n"
                    output += "└─ Reenvía cualquier archivo al canal para descargarlo\n\n"
                    output += f"💡 Versión: {TDD_VERSION}"

                elif command == "config":
                    output = "⚙️  **CONFIGURACIÓN ACTUAL**\n\n"
                    output += f"👤 **Cuenta:**\n"
                    output += f"├─ Tipo: {'Premium ⭐' if is_premium_account else 'Estándar 📱'}\n"
                    output += f"├─ Límite archivo: {max_file_size} MB\n"
                    output += f"└─ Workers: {worker_count}\n\n"
                    output += f"📂 **Rutas:**\n"
                    output += f"├─ Descargas: `{downloadFolder}`\n"
                    output += f"└─ Temporal: `{tempFolder}`\n\n"
                    output += f"🔧 **Opciones:**\n"
                    output += f"├─ Duplicados: `{duplicates}`\n"
                    if TELEGRAM_DAEMON_FILE_FILTER:
                        output += f"├─ Filtros: `{TELEGRAM_DAEMON_FILE_FILTER}`\n"
                    output += f"└─ Estado: {'⏸️ Pausado' if download_paused else '▶️ Activo'}\n\n"
                    if is_premium_account:
                        output += f"✨ **Optimizaciones Premium:**\n"
                        output += f"├─ Sin límites de velocidad\n"
                        output += f"├─ Chunks optimizados\n"
                        output += f"└─ Paralelismo mejorado"

                elif command == "stats":
                    uptime = datetime.now() - stats['session_start']
                    avg_speed = sum(stats['download_speeds'][-10:]) / len(stats['download_speeds'][-10:]) if stats['download_speeds'] else 0

                    output = "📊 **ESTADÍSTICAS DE SESIÓN**\n\n"
                    output += f"⏱️ **Tiempo activo:** {format_time(uptime.total_seconds())}\n"
                    output += f"📅 **Inicio:** {stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    output += f"📥 **Descargas:**\n"
                    output += f"├─ Total: {stats['total_downloads']}\n"
                    output += f"├─ Exitosas: {stats['successful_downloads']} ✅\n"
                    output += f"├─ Fallidas: {stats['failed_downloads']} ❌\n"
                    if stats['total_downloads'] > 0:
                        success_rate = (stats['successful_downloads'] / stats['total_downloads']) * 100
                        output += f"└─ Tasa éxito: {success_rate:.1f}%\n\n"

                    output += f"💾 **Datos:**\n"
                    output += f"├─ Total descargado: {format_bytes(stats['total_bytes'])}\n"
                    if avg_speed > 0:
                        output += f"├─ Velocidad promedio: {format_speed(avg_speed)}\n"
                    if stats['largest_file']['name']:
                        output += f"└─ Archivo más grande:\n"
                        output += f"    • {stats['largest_file']['name']}\n"
                        output += f"    • {format_bytes(stats['largest_file']['size'])}\n"

                elif command == "list":
                    output = subprocess.run(["ls -lh "+downloadFolder], shell=True, stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode('utf-8')
                    if output:
                        output = f"📁 **Archivos descargados:**\n\n```\n{output}\n```"
                    else:
                        output = "📁 La carpeta de descargas está vacía"

                elif command == "status":
                    try:
                        if in_progress:
                            output = "📥 **DESCARGAS ACTIVAS:**\n\n"
                            for filename, progress in in_progress.items():
                                output += f"📄 **{filename}**\n{progress}\n\n"
                        else:
                            output = "✅ **Sin descargas activas**\n\n"

                        # Información de cuenta
                        output += f"{'─'*40}\n"
                        output += f"🏷️ **INFORMACIÓN DE CUENTA**\n\n"
                        output += f"👤 Tipo: **{'Premium ⭐' if is_premium_account else 'Estándar 📱'}**\n"
                        output += f"📁 Límite: **{max_file_size} MB**\n"
                        output += f"🔄 Workers: **{worker_count}**\n"
                        output += f"📊 Estado: **{'⏸️ Pausado' if download_paused else '▶️ Activo'}**\n"

                        if is_premium_account:
                            output += f"\n⚡ **Optimizaciones Premium activas**"
                        else:
                            output += f"\n💡 Considera Premium para mejor rendimiento"

                    except Exception as e:
                        output = f"❌ Error al verificar estado: {str(e)}"

                elif command == "pause":
                    global download_paused
                    download_paused = True
                    output = "⏸️ **Descargas pausadas**\n\n"
                    output += "Las descargas actuales continuarán, pero no se procesarán nuevos archivos de la cola.\n\n"
                    output += "Escribe `resume` para reanudar."

                elif command == "resume":
                    download_paused = False
                    output = "▶️ **Descargas reanudadas**\n\n"
                    output += "El procesamiento de la cola se ha reactivado."

                elif command == "clean":
                    output = "🧹 **Limpiando archivos temporales...**\n\n"
                    output += f"📂 Carpeta: `{tempFolder}`\n\n"
                    result = subprocess.run(
                        "rm " + tempFolder + "/*." + TELEGRAM_DAEMON_TEMP_SUFFIX,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    ).stdout.decode("utf-8")
                    output += f"```\n{result if result else 'Sin archivos temporales para eliminar'}\n```\n"
                    output += "✅ Limpieza completada"

                elif command == "queue":
                    try:
                        files_in_queue = []
                        for q in queue.__dict__['_queue']:
                            files_in_queue.append(getFilename(q[0]))

                        if files_in_queue:
                            output = f"📋 **ARCHIVOS EN COLA ({len(files_in_queue)})**\n\n"
                            for i, filename in enumerate(files_in_queue, 1):
                                output += f"{i}. {filename}\n"
                        else:
                            output = "✅ **La cola está vacía**\n\n"
                            output += "Reenvía archivos al canal para añadirlos a la cola."
                    except Exception as e:
                        output = f"❌ Error al verificar cola: {str(e)}"
                else:
                    output = "❓ **Comando no reconocido**\n\n"
                    output += "Escribe `help` para ver los comandos disponibles."

                await log_reply(event, output)

            if event.media:
                if hasattr(event.media, 'document') or hasattr(event.media,'photo'):
                    filename=getFilename(event)

                    # Verificar filtros de archivo
                    if not is_file_allowed(filename):
                        await event.reply(f"⏭️ **Archivo filtrado**\n\n"
                                        f"📄 {filename}\n"
                                        f"🎯 Extensiones permitidas: `{TELEGRAM_DAEMON_FILE_FILTER}`")
                        return

                    # Verificar tamaño del archivo
                    if hasattr(event.media, 'document'):
                        file_size_mb = event.media.document.size / (1024 * 1024)

                        if not is_premium_account and file_size_mb > 2000:
                            message = await event.reply(
                                f"❌ **ARCHIVO DEMASIADO GRANDE**\n\n"
                                f"📄 **Archivo:** {filename}\n"
                                f"📦 **Tamaño:** {file_size_mb:.2f} MB\n"
                                f"⚠️  **Límite actual:** 2,000 MB\n\n"
                                f"{'─'*40}\n"
                                f"💡 **SOLUCIÓN**\n"
                                f"Actualiza a Telegram Premium para:\n"
                                f"• Archivos hasta 4GB\n"
                                f"• Velocidad sin límites\n"
                                f"• Prioridad en descargas\n\n"
                                f"📎 https://telegram.org/premium"
                            )
                            return
                        elif file_size_mb > max_file_size:
                            message = await event.reply(
                                f"❌ **Archivo excede límite configurado**\n\n"
                                f"📄 **Archivo:** {filename}\n"
                                f"📦 **Tamaño:** {file_size_mb:.2f} MB\n"
                                f"⚠️  **Límite:** {max_file_size} MB"
                            )
                            return

                        # Archivo válido
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or
                             path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply(f"⏭️ **{filename}** ya existe. Ignorando.")
                        else:
                            stats['total_downloads'] += 1
                            queue_size = queue.qsize()

                            message_text = f"✅ **Añadido a la cola**\n\n"
                            message_text += f"📄 **Archivo:** {filename}\n"
                            message_text += f"📦 **Tamaño:** {format_bytes(event.media.document.size)}\n"
                            message_text += f"📋 **Posición en cola:** {queue_size + 1}\n"
                            if is_premium_account and file_size_mb > 2000:
                                message_text += f"\n⭐ **Premium:** Archivo grande detectado"

                            message=await event.reply(message_text)
                            await queue.put([event, message])
                    else:
                        # Fotos
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or
                             path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply(f"⏭️ **{filename}** ya existe. Ignorando.")
                        else:
                            stats['total_downloads'] += 1
                            message=await event.reply(f"✅ **{filename}** añadido a la cola")
                            await queue.put([event, message])
                else:
                    message=await event.reply("❌ **No descargable**\n\nEnvía el archivo como documento.")

        except Exception as e:
                print('Events handler error: ', e)

    async def worker():
        """Worker mejorado con reintentos y mejor manejo de errores"""
        while True:
            try:
                # Verificar si está pausado
                while download_paused:
                    await asyncio.sleep(5)

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

                # Mensaje de inicio de descarga mejorado
                download_info = f"🚀 **INICIANDO DESCARGA**\n\n"
                download_info += f"📄 **Archivo:** {filename}\n"
                download_info += f"📦 **Tamaño:** {format_bytes(size)}"

                if size_mb > 0:
                    download_info += f" ({size_mb:.2f} MB)"

                download_info += f"\n🔄 **Modo:** {'Premium ⭐' if is_premium_account else 'Estándar 📱'}\n"

                if is_premium_account and size_mb > 2000:
                    download_info += f"\n💎 **Archivo grande Premium detectado**"

                await log_reply(message, download_info)

                # Registrar tiempo de inicio
                download_start_times[filename] = time.time()

                download_callback = lambda received, total: set_progress(filename, message, received, total)

                # Intentar descarga con reintentos
                max_retries = 3
                retry_count = 0
                download_success = False

                while retry_count < max_retries and not download_success:
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

                        if retry_count < max_retries:
                            wait_time = retry_count * 5
                            await log_reply(message,
                                f"⚠️ **Reintento {retry_count}/{max_retries}**\n\n"
                                f"Error: {error_msg}\n"
                                f"Esperando {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            raise download_error

                # Descarga completada exitosamente
                set_progress(filename, message, 100, 100)
                move("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX),
                     "{0}/{1}".format(downloadFolder,filename))

                # Actualizar estadísticas
                stats['successful_downloads'] += 1
                stats['total_bytes'] += size

                if size > stats['largest_file']['size']:
                    stats['largest_file'] = {'name': filename, 'size': size}

                # Calcular tiempo y velocidad
                download_time = time.time() - download_start_times.get(filename, time.time())
                avg_speed = size / download_time if download_time > 0 else 0

                # Mensaje de finalización mejorado
                completion_msg = f"✅ **DESCARGA COMPLETADA**\n\n"
                completion_msg += f"📄 **Archivo:** {filename}\n"
                completion_msg += f"📦 **Tamaño:** {format_bytes(size)}"

                if size_mb > 1:
                    completion_msg += f" ({size_mb:.2f} MB)"

                completion_msg += f"\n⏱️ **Tiempo:** {format_time(download_time)}\n"

                if avg_speed > 0:
                    completion_msg += f"⚡ **Velocidad promedio:** {format_speed(avg_speed)}\n"

                completion_msg += f"📁 **Ubicación:** `{downloadFolder}`\n\n"
                completion_msg += f"{'─'*40}\n"
                completion_msg += f"✨ Descarga #{stats['successful_downloads']} de esta sesión"

                await log_reply(message, completion_msg)

                queue.task_done()

            except Exception as e:
                stats['failed_downloads'] += 1

                try:
                    error_msg = f"❌ **ERROR EN DESCARGA**\n\n"
                    error_msg += f"📄 **Archivo:** {filename}\n"
                    error_msg += f"🚨 **Error:** {str(e)}\n"
                    error_msg += f"🔄 **Reintentos agotados:** {max_retries}\n\n"

                    # Sugerencias específicas
                    error_lower = str(e).lower()
                    if "file too large" in error_lower or "flood" in error_lower:
                        if not is_premium_account:
                            error_msg += f"💡 **Solución sugerida:**\n"
                            error_msg += f"Actualiza a Premium para:\n"
                            error_msg += f"• Archivos hasta 4GB\n"
                            error_msg += f"• Sin límites de velocidad\n"
                            error_msg += f"• Reintentos automáticos mejorados\n\n"
                            error_msg += f"📎 https://telegram.org/premium"
                        else:
                            error_msg += f"💡 El archivo será omitido."
                    elif "timeout" in error_lower:
                        error_msg += f"💡 **Problema de red**\n"
                        error_msg += f"Verifica tu conexión a internet."

                    await log_reply(message, error_msg)
                except:
                    pass

                print(f'Queue worker error: {e}')
                queue.task_done()

    async def start():
        """Inicio del daemon"""
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
