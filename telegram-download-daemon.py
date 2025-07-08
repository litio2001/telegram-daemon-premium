#!/usr/bin/env python3
# Telegram Download Daemon
# Author: Alfonso E.M. <alfonso@el-magnifico.org>
# You need to install telethon (and cryptg to speed up downloads)

from os import getenv, path
from shutil import move
import subprocess
import math
import time
import random
import string
import os.path
from mimetypes import guess_extension

from sessionManager import getSession, saveSession

from telethon import TelegramClient, events, __version__
from telethon.tl.types import PeerChannel, DocumentAttributeFilename, DocumentAttributeVideo
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s]%(name)s:%(message)s',
                    level=logging.WARNING)

import multiprocessing
import argparse
import asyncio


TDD_VERSION="1.15"  # Actualizar versión para reflejar soporte Premium

TELEGRAM_DAEMON_API_ID = getenv("TELEGRAM_DAEMON_API_ID")
TELEGRAM_DAEMON_API_HASH = getenv("TELEGRAM_DAEMON_API_HASH")
TELEGRAM_DAEMON_CHANNEL = getenv("TELEGRAM_DAEMON_CHANNEL")

TELEGRAM_DAEMON_SESSION_PATH = getenv("TELEGRAM_DAEMON_SESSION_PATH")

TELEGRAM_DAEMON_DEST=getenv("TELEGRAM_DAEMON_DEST", "/telegram-downloads")
TELEGRAM_DAEMON_TEMP=getenv("TELEGRAM_DAEMON_TEMP", "")
TELEGRAM_DAEMON_DUPLICATES=getenv("TELEGRAM_DAEMON_DUPLICATES", "rename")

TELEGRAM_DAEMON_TEMP_SUFFIX="tdd"

TELEGRAM_DAEMON_WORKERS=getenv("TELEGRAM_DAEMON_WORKERS", multiprocessing.cpu_count())

# Añadir nuevas variables de entorno para Premium
TELEGRAM_DAEMON_PREMIUM_MAX_SIZE=getenv("TELEGRAM_DAEMON_PREMIUM_MAX_SIZE", "4000")  # MB

# Variables globales para Premium - DECLARAR AQUÍ
is_premium_account = False
max_file_size = 2000  # MB por defecto (límite no Premium)

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

async def check_premium_status(client):
    """
    Verifica si la cuenta actual es Premium usando múltiples métodos.
    Basado en la documentación oficial de Telegram API (Layer 195).
    
    Según el schema oficial: user#83314fca flags:# premium:flags.28?true
    """
    try:
        # Obtener información del usuario actual
        me = await client.get_me()
        
        print(f"🔍 Checking Premium status for user: {getattr(me, 'first_name', 'Unknown')}")
        print(f"   User ID: {me.id}")
        print(f"   Username: @{getattr(me, 'username', 'no_username')}")
        
        # Método 1: Verificar atributo premium directamente (más confiable)
        if hasattr(me, 'premium') and me.premium is not None:
            is_premium = bool(me.premium)
            print(f"✅ Premium status detected via direct attribute: {is_premium}")
            return is_premium
        
        # Método 2: Usar getattr con valor por defecto
        premium_attr = getattr(me, 'premium', None)
        if premium_attr is not None:
            is_premium = bool(premium_attr)
            print(f"✅ Premium status detected via getattr: {is_premium}")
            return is_premium
        
        # Método 3: Verificar flags manualmente (bit 28 según documentación oficial)
        if hasattr(me, 'flags') and me.flags is not None:
            # Según schema oficial: premium:flags.28?true
            premium_flag = bool(me.flags & (1 << 28))
            print(f"✅ Premium status via flags bit 28: {premium_flag}")
            print(f"   Raw flags: {hex(me.flags)} (binary: {bin(me.flags)})")
            return premium_flag
        
        # Si no hay información disponible, asumir cuenta estándar
        print("⚠️  No premium indicators found - assuming Standard account")
        print("   This might be due to an older Telethon version or API limitations")
        return False
        
    except Exception as e:
        print(f"❌ Error checking premium status: {type(e).__name__}: {e}")
        print("   Defaulting to Standard account")
        return False

async def sendHelloMessage(client, peerChannel):
    global is_premium_account, max_file_size
    
    entity = await client.get_entity(peerChannel)
    
    # Verificar si la cuenta es Premium usando método robusto
    is_premium_account = await check_premium_status(client)
    
    # Configurar parámetros según el tipo de cuenta
    if is_premium_account:
        max_file_size = int(TELEGRAM_DAEMON_PREMIUM_MAX_SIZE)
        account_type = "Premium ⭐"
        features = "✅ Large files, ✅ Fast speeds, ✅ Premium features"
    else:
        max_file_size = 2000
        account_type = "Standard"
        features = "⚡ Standard speeds, 📁 Basic features"
    
    print(f"")
    print(f"🚀 Telegram Download Daemon {TDD_VERSION}")
    print(f"📱 Telethon {__version__}")
    print(f"👤 Account type: {account_type}")
    print(f"📁 Max file size: {max_file_size} MB")
    print(f"🔄 Workers: {str(worker_count)}")
    print(f"✨ Features: {features}")
    print(f"")
    
    # Mensaje de bienvenida detallado
    hello_msg = f"🚀 **Telegram Download Daemon {TDD_VERSION}**\n"
    hello_msg += f"📱 Telethon {__version__}\n\n"
    hello_msg += f"👤 **Account:** {account_type}\n"
    hello_msg += f"📁 **Max file size:** {max_file_size} MB\n"
    hello_msg += f"🔄 **Workers:** {str(worker_count)}\n"
    hello_msg += f"✨ **Features:** {features}\n\n"
    hello_msg += f"⚡ **Ready for downloads!**"
    
    await client.send_message(entity, hello_msg)
 

async def log_reply(message, reply):
    print(reply)
    await message.edit(reply)

def getRandomId(len):
    chars=string.ascii_lowercase + string.digits
    return  ''.join(random.choice(chars) for x in range(len))
 
def getFilename(event: events.NewMessage.Event):
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


in_progress={}

async def set_progress(filename, message, received, total):
    global lastUpdate
    global updateFrequency

    if received >= total:
        try: in_progress.pop(filename)
        except: pass
        return
    percentage = math.trunc(received / total * 10000) / 100

    progress_message= "{0} % ({1} / {2})".format(percentage, received, total)
    in_progress[filename] = progress_message

    currentTime=time.time()
    if (currentTime - lastUpdate) > updateFrequency:
        await log_reply(message, progress_message)
        lastUpdate=currentTime


with TelegramClient(getSession(), api_id, api_hash,
                    proxy=proxy).start() as client:

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

                if command == "list":
                    output = subprocess.run(["ls -l "+downloadFolder], shell=True, stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode('utf-8')
                elif command == "status":
                    try:
                        output = "".join([ "{0}: {1}\n".format(key,value) for (key, value) in in_progress.items()])
                        if output: 
                            output = "Active downloads:\n\n" + output
                        else: 
                            output = "No active downloads"
                        # Añadir información de Premium
                        output += f"\n\nAccount type: {'Premium' if is_premium_account else 'Standard'}"
                        output += f"\nMax file size: {max_file_size} MB"
                    except:
                        output = "Some error occured while checking the status. Retry."
                elif command == "clean":
                    output = "Cleaning " + tempFolder + "\n"
                    output += subprocess.run(
                        "rm " + tempFolder + "/*." + TELEGRAM_DAEMON_TEMP_SUFFIX,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    ).stdout.decode("utf-8")
                elif command == "queue":
                    try:
                        files_in_queue = []
                        for q in queue.__dict__['_queue']:
                            files_in_queue.append(getFilename(q[0]))
                        output = "".join([ "{0}\n".format(filename) for (filename) in files_in_queue])
                        if output: 
                            output = "Files in queue:\n\n" + output
                        else: 
                            output = "Queue is empty"
                    except:
                        output = "Some error occured while checking the queue. Retry."
                else:
                    output = "Available commands: list, status, clean, queue"

                await log_reply(event, output)

            if event.media:
                if hasattr(event.media, 'document') or hasattr(event.media,'photo'):
                    filename=getFilename(event)
                    
                    # Verificar tamaño del archivo para cuentas no Premium
                    if hasattr(event.media, 'document'):
                        file_size_mb = event.media.document.size / (1024 * 1024)
                        if not is_premium_account and file_size_mb > 2000:
                            message = await event.reply(f"❌ File {filename} is too large ({file_size_mb:.2f} MB). Premium account required for files >2GB.")
                        elif file_size_mb > max_file_size:
                            message = await event.reply(f"❌ File {filename} exceeds maximum size ({file_size_mb:.2f} MB > {max_file_size} MB).")
                        else:
                            # Solo procesar si el archivo tiene un tamaño válido
                            if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                                message=await event.reply("{0} already exists. Ignoring it.".format(filename))
                            else:
                                message=await event.reply("{0} added to queue".format(filename))
                                await queue.put([event, message])
                    else:
                        # Para fotos, procesar normalmente
                        if ( path.exists("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX)) or path.exists("{0}/{1}".format(downloadFolder,filename)) ) and duplicates == "ignore":
                            message=await event.reply("{0} already exists. Ignoring it.".format(filename))
                        else:
                            message=await event.reply("{0} added to queue".format(filename))
                            await queue.put([event, message])
                else:
                    message=await event.reply("That is not downloadable. Try to send it as a file.")

        except Exception as e:
                print('Events handler error: ', e)

    async def worker():
        while True:
            try:
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

                # Mostrar información adicional para archivos grandes
                size_mb = size / (1024 * 1024)
                download_info = "Downloading file {0} ({1} bytes".format(filename, size)
                if size_mb > 100:
                    download_info += " / {:.2f} MB".format(size_mb)
                download_info += ")"
                if is_premium_account and size_mb > 2000:
                    download_info += " [Premium]"
                
                await log_reply(message, download_info)

                download_callback = lambda received, total: set_progress(filename, message, received, total)

                # Nota: chunk_size no es un parámetro soportado en download_media de Telethon
                # Telethon maneja automáticamente el tamaño de chunk basado en la conexión
                # Las optimizaciones Premium se aplican a través de otros métodos
                
                await client.download_media(
                    event.message, 
                    "{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX), 
                    progress_callback = download_callback
                )
                set_progress(filename, message, 100, 100)
                move("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX), "{0}/{1}".format(downloadFolder,filename))
                await log_reply(message, "{0} ready".format(filename))

                queue.task_done()
            except Exception as e:
                try: 
                    error_msg = "Error: {}".format(str(e))
                    # Añadir sugerencia si el error está relacionado con el tamaño
                    if "file too large" in str(e).lower() and not is_premium_account:
                        error_msg += "\n💡 Consider upgrading to Premium for large files."
                    await log_reply(message, error_msg)
                except: pass
                print('Queue worker error: ', e)
 
    async def start():

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
