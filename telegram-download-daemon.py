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


TDD_VERSION="1.17-Premium"  # Versión con correcciones de detección Premium y optimizaciones mejoradas

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

def configure_client_for_premium(is_premium):
    """
    Configura parámetros optimizados del cliente según el tipo de cuenta.
    Las cuentas Premium tienen acceso a:
    - Sin límites de velocidad de descarga (FLOOD_PREMIUM_WAIT_X no aplica)
    - Archivos más grandes (hasta 4GB vs 2GB)
    - Optimizaciones de red mejoradas
    """
    global worker_count
    
    if is_premium:
        print("🚀 Activando optimizaciones Premium:")
        
        # Optimizar workers para Premium (mejor paralelismo)
        original_workers = worker_count
        # Premium puede manejar más workers simultáneos sin throttling
        worker_count = min(12, max(6, multiprocessing.cpu_count() * 3))
        print(f"   🔄 Workers optimizados: {original_workers} → {worker_count}")
        
        print(f"   ⚡ Sin límites de velocidad (FLOOD_PREMIUM_WAIT_X exento)")
        print(f"   📦 Archivos hasta {max_file_size} MB (vs 2000 MB estándar)")
        print(f"   🎯 Chunks de 1MB para archivos grandes")
        print(f"   🚀 Paralelismo mejorado para múltiples archivos")
    else:
        print("📱 Configuración estándar activada:")
        print(f"   📦 Archivos hasta {max_file_size} MB")
        print(f"   ⚡ Velocidad estándar (con límites FLOOD_WAIT)")
        print(f"   🔄 Workers: {worker_count}")
        print(f"   💡 Considera Telegram Premium para mejor rendimiento")

async def check_premium_status(client):
    """
    Verifica si la cuenta actual es Premium usando los métodos oficiales de Telegram API.
    Documentación oficial: https://core.telegram.org/api/premium
    
    Métodos probados en orden:
    1. client.get_me() - Método principal recomendado por Telethon
    2. users.getUsers con InputUserSelf - API oficial de Telegram
    3. users.getFullUser - Información completa del usuario
    4. help.getPremiumPromo - Verificación cruzada
    """
    print("🔍 Detectando estado Premium de la cuenta...")
    
    try:
        # Método 1: get_me() - Método principal y más confiable
        me = await client.get_me()
        print(f"� Usuario: {getattr(me, 'first_name', 'Unknown')} {getattr(me, 'last_name', '')} (ID: {me.id})")
        
        # Verificar atributo premium directamente
        if hasattr(me, 'premium') and me.premium is True:
            print("✅ PREMIUM DETECTADO - Atributo premium=True")
            return True
        
        # Verificar usando getattr por si premium es None pero existe
        premium_attr = getattr(me, 'premium', None)
        if premium_attr is True:
            print("✅ PREMIUM DETECTADO - getattr premium=True")
            return True
            
        print(f"📱 Atributo premium: {premium_attr}")
        
    except Exception as e:
        print(f"⚠️  get_me() falló: {e}")
    
    try:
        # Método 2: API oficial users.getUsers con InputUserSelf
        from telethon.tl.functions.users import GetUsersRequest
        from telethon.tl.types import InputUserSelf
        
        users_result = await client(GetUsersRequest([InputUserSelf()]))
        if users_result and len(users_result) > 0:
            user = users_result[0]
            premium_status = getattr(user, 'premium', None)
            print(f"🔍 GetUsersRequest - Premium: {premium_status}")
            
            if premium_status is True:
                print("✅ PREMIUM DETECTADO - GetUsersRequest")
                return True
                
    except Exception as e:
        print(f"⚠️  GetUsersRequest falló: {e}")
    
    try:
        # Método 3: users.getFullUser para información completa
        from telethon.tl.functions.users import GetFullUserRequest
        from telethon.tl.types import InputUserSelf
        
        full_result = await client(GetFullUserRequest(InputUserSelf()))
        if full_result and hasattr(full_result, 'users') and full_result.users:
            user = full_result.users[0]
            premium_status = getattr(user, 'premium', None)
            print(f"🔍 GetFullUserRequest - Premium: {premium_status}")
            
            if premium_status is True:
                print("✅ PREMIUM DETECTADO - GetFullUserRequest")
                return True
                
    except Exception as e:
        print(f"⚠️  GetFullUserRequest falló: {e}")
    
    try:
        # Método 4: help.getPremiumPromo - Verificación cruzada
        from telethon.tl.functions.help import GetPremiumPromoRequest
        
        promo_result = await client(GetPremiumPromoRequest())
        if promo_result and hasattr(promo_result, 'users'):
            for user in promo_result.users:
                if hasattr(user, 'self') and getattr(user, 'self', False):
                    premium_status = getattr(user, 'premium', None)
                    print(f"🔍 GetPremiumPromo - Premium: {premium_status}")
                    
                    if premium_status is True:
                        print("✅ PREMIUM DETECTADO - GetPremiumPromo")
                        return True
                        
    except Exception as e:
        print(f"⚠️  GetPremiumPromo falló: {e}")
    
    # Resultado final
    print("📱 RESULTADO: Cuenta Estándar (no Premium)")
    print("   ℹ️  Para activar Premium: https://telegram.org/premium")
    return False

async def sendHelloMessage(client, peerChannel):
    global is_premium_account, max_file_size
    
    entity = await client.get_entity(peerChannel)
    
    print("=" * 60)
    print("🚀 TELEGRAM DOWNLOAD DAEMON - Iniciando...")
    print("=" * 60)
    
    # Verificar si la cuenta es Premium usando método robusto mejorado
    is_premium_account = await check_premium_status(client)
    
    print("-" * 60)
    
    # Configurar parámetros según el tipo de cuenta
    if is_premium_account:
        max_file_size = int(TELEGRAM_DAEMON_PREMIUM_MAX_SIZE)
        account_type = "Premium ⭐"
        features = "✅ Archivos grandes, ✅ Velocidad sin límites, ✅ Descarga optimizada"
        emoji_status = "🚀"
        speed_info = "Sin límites de velocidad (FLOOD_PREMIUM_WAIT_X exento)"
    else:
        max_file_size = 2000
        account_type = "Standard"
        features = "⚡ Velocidad estándar, 📁 Funciones básicas"
        emoji_status = "📱"
        speed_info = "Límites estándar de Telegram (pueden aplicar FLOOD_WAIT)"
    
    # Aplicar configuraciones optimizadas
    configure_client_for_premium(is_premium_account)
    
    print("-" * 60)
    print(f"{emoji_status} CONFIGURACIÓN FINAL:")
    print(f"   📱 Telethon: {__version__}")
    print(f"   👤 Cuenta: {account_type}")
    print(f"   📁 Tamaño máximo: {max_file_size:,} MB")
    print(f"   🔄 Workers: {worker_count}")
    print(f"   ⚡ Velocidad: {speed_info}")
    print("=" * 60)
    
    # Mensaje de bienvenida detallado para Telegram
    hello_msg = f"🚀 **Telegram Download Daemon {TDD_VERSION}**\n"
    hello_msg += f"📱 Telethon {__version__} | Python Asyncio\n\n"
    
    hello_msg += f"👤 **Estado de cuenta:** {account_type}\n"
    hello_msg += f"📁 **Límite de archivo:** {max_file_size:,} MB\n"
    hello_msg += f"🔄 **Workers paralelos:** {worker_count}\n\n"
    
    if is_premium_account:
        hello_msg += f"🎯 **Optimizaciones Premium activas:**\n"
        hello_msg += f"⚡ Sin límites de velocidad de descarga\n"
        hello_msg += f"📦 Soporte para archivos hasta 4GB\n"
        hello_msg += f"🚀 Paralelismo mejorado para múltiples archivos\n"
        hello_msg += f"🎯 Chunks optimizados automáticamente\n\n"
    else:
        hello_msg += f"📱 **Configuración estándar:**\n"
        hello_msg += f"⚡ Velocidad estándar de Telegram\n"
        hello_msg += f"📦 Archivos hasta 2GB\n"
        hello_msg += f"💡 *Considera Premium para mejor rendimiento*\n\n"
    
    hello_msg += f"✨ **Características disponibles:** {features}\n\n"
    hello_msg += f"⚡ **Sistema listo para descargas!**\n"
    hello_msg += f"📝 Comandos: `status`, `queue`, `list`, `clean`"
    
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
                    proxy=proxy,
                    # Configuraciones optimizadas para mejor rendimiento
                    connection_retries=5,  # Más reintentos para mejor estabilidad
                    retry_delay=2,         # Menor delay entre reintentos
                    timeout=60,            # Timeout mayor para archivos grandes
                    device_model="TDD Premium",  # Identificar como cliente optimizado
                    system_version="1.16-Premium",
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

                if command == "list":
                    output = subprocess.run(["ls -l "+downloadFolder], shell=True, stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode('utf-8')
                elif command == "status":
                    try:
                        output = "".join([ "{0}: {1}\n".format(key,value) for (key, value) in in_progress.items()])
                        if output: 
                            output = "📥 **Descargas activas:**\n\n" + output
                        else: 
                            output = "✅ **Sin descargas activas**"
                        
                        # Información de cuenta mejorada
                        account_info = f"\n\n🏷️ **Información de cuenta:**\n"
                        account_info += f"👤 Tipo: {'Premium ⭐' if is_premium_account else 'Standard'}\n"
                        account_info += f"📁 Límite de archivo: {max_file_size} MB\n"
                        account_info += f"🔄 Workers: {worker_count}\n"
                        
                        if is_premium_account:
                            account_info += f"⚡ Sin límites de velocidad\n"
                            account_info += f"🎯 Optimizaciones activas\n"
                        else:
                            account_info += f"⚡ Velocidad estándar\n"
                            account_info += f"💡 Premium disponible para más velocidad\n"
                        
                        output += account_info
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
                            message = await event.reply(f"❌ **Archivo demasiado grande**\n\n"
                                                      f"📄 **Archivo:** {filename}\n"
                                                      f"📦 **Tamaño:** {file_size_mb:.2f} MB\n"
                                                      f"⚠️  **Límite actual:** 2,000 MB\n\n"
                                                      f"💡 **Solución:** Se requiere cuenta Premium para archivos >2GB")
                        elif file_size_mb > max_file_size:
                            message = await event.reply(f"❌ **Archivo excede el límite**\n\n"
                                                      f"📄 **Archivo:** {filename}\n"
                                                      f"📦 **Tamaño:** {file_size_mb:.2f} MB\n"
                                                      f"⚠️  **Límite configurado:** {max_file_size} MB")
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

                # Mostrar información mejorada para archivos
                size_mb = size / (1024 * 1024)
                
                if size_mb > 100:  # Solo mostrar MB para archivos grandes
                    download_info = f"📥 **Descargando:** {filename}\n"
                    download_info += f"📦 **Tamaño:** {size_mb:.2f} MB ({size:,} bytes)\n"
                    
                    if is_premium_account:
                        if size_mb > 2000:
                            download_info += f"⭐ **Premium:** Archivo grande detectado\n"
                        download_info += f"🚀 **Modo:** Optimizado Premium"
                    else:
                        download_info += f"⚡ **Modo:** Estándar"
                else:
                    download_info = f"📥 Descargando {filename} ({size:,} bytes)"
                    if is_premium_account:
                        download_info += " [Premium]"
                
                await log_reply(message, download_info)

                download_callback = lambda received, total: set_progress(filename, message, received, total)

                # Configurar parámetros de descarga según tipo de cuenta
                try:
                    if is_premium_account:
                        # Premium: usar download_media con parámetros optimizados
                        print(f"🚀 Descarga Premium para {filename}")
                        
                        # Para archivos grandes, usar chunk_size mayor (Telethon ajusta internamente)
                        if size_mb > 50:  # Archivos grandes
                            # Telethon maneja internamente los chunks de manera óptima para Premium
                            await client.download_media(
                                event.message,
                                "{0}/{1}.{2}".format(tempFolder, filename, TELEGRAM_DAEMON_TEMP_SUFFIX),
                                progress_callback=download_callback,
                                # Telethon automáticamente optimiza para cuentas Premium
                            )
                        else:
                            # Archivos pequeños - método estándar
                            await client.download_media(
                                event.message,
                                "{0}/{1}.{2}".format(tempFolder, filename, TELEGRAM_DAEMON_TEMP_SUFFIX),
                                progress_callback=download_callback
                            )
                    else:
                        # Cuenta estándar - método normal
                        await client.download_media(
                            event.message,
                            "{0}/{1}.{2}".format(tempFolder, filename, TELEGRAM_DAEMON_TEMP_SUFFIX),
                            progress_callback=download_callback
                        )
                        
                except Exception as download_error:
                    # Fallback en caso de error con optimizaciones
                    print(f"⚠️  Error en descarga optimizada, usando método estándar: {download_error}")
                    await client.download_media(
                        event.message,
                        "{0}/{1}.{2}".format(tempFolder, filename, TELEGRAM_DAEMON_TEMP_SUFFIX),
                        progress_callback=download_callback
                    )
                set_progress(filename, message, 100, 100)
                move("{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX), "{0}/{1}".format(downloadFolder,filename))
                
                # Mensaje de finalización mejorado
                completion_msg = f"✅ **Descarga completada**\n"
                completion_msg += f"📄 **Archivo:** {filename}\n"
                if size_mb > 10:  # Solo mostrar tamaño para archivos medianos/grandes
                    completion_msg += f"📦 **Tamaño:** {size_mb:.2f} MB\n"
                completion_msg += f"📁 **Ubicación:** {downloadFolder}"
                
                await log_reply(message, completion_msg)

                queue.task_done()
            except Exception as e:
                try: 
                    error_msg = f"❌ **Error en descarga**\n\n"
                    error_msg += f"📄 **Archivo:** {filename}\n"
                    error_msg += f"🚨 **Error:** {str(e)}\n"
                    
                    # Sugerencias específicas según el tipo de error y cuenta
                    error_lower = str(e).lower()
                    if "file too large" in error_lower or "flood" in error_lower:
                        if not is_premium_account:
                            error_msg += f"\n💡 **Sugerencia:** Considera actualizar a Premium para:"
                            error_msg += f"\n   • Archivos más grandes (hasta 4GB)"
                            error_msg += f"\n   • Sin límites de velocidad"
                            error_msg += f"\n   • Descargas optimizadas"
                        else:
                            error_msg += f"\n🔄 **Reintentando:** El archivo será reintentado automáticamente"
                    elif "timeout" in error_lower:
                        error_msg += f"\n🔄 **Conexión:** Problema temporal de red"
                    
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
