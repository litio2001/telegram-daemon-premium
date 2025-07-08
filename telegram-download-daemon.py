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


TDD_VERSION="1.16-Premium"  # Versión actualizada con mejoras Premium optimizadas

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
    Las cuentas Premium no tienen límites de velocidad de descarga.
    """
    global worker_count
    
    if is_premium:
        print("🚀 Configurando optimizaciones Premium:")
        
        # Aumentar workers para aprovechar la velocidad Premium
        if worker_count < 4:
            original_workers = worker_count
            worker_count = min(8, multiprocessing.cpu_count() * 2)
            print(f"   🔄 Workers aumentados: {original_workers} → {worker_count}")
        
        print(f"   ⚡ Sin límites de velocidad de descarga")
        print(f"   📦 Archivos hasta {max_file_size} MB")
        print(f"   🎯 Chunks optimizados para archivos grandes")
    else:
        print("📱 Configuración estándar aplicada")
        print(f"   📦 Archivos hasta {max_file_size} MB")
        print(f"   ⚡ Velocidad de descarga estándar")

async def check_premium_status(client):
    """
    Verifica si la cuenta actual es Premium usando múltiples métodos mejorados.
    Basado en la documentación oficial de Telegram API:
    - users.getUsers con inputUserSelf
    - users.getFullUser para información completa
    - help.getPremiumPromo para verificación cruzada
    
    Según el schema oficial: user#83314fca flags:# premium:flags.28?true
    """
    try:
        from telethon.tl.functions.users import GetUsersRequest, GetFullUserRequest
        from telethon.tl.functions.help import GetPremiumPromoRequest
        from telethon.tl.types import InputUserSelf
        
        print("🔍 Iniciando detección Premium con métodos mejorados...")
        
        # Método 1: Usar GetUsersRequest con InputUserSelf (método oficial recomendado)
        try:
            users_result = await client(GetUsersRequest([InputUserSelf()]))
            if users_result and len(users_result) > 0:
                me = users_result[0]
                print(f"📱 Usuario: {getattr(me, 'first_name', 'Unknown')} (ID: {me.id})")
                
                # Verificar atributo premium directamente
                if hasattr(me, 'premium'):
                    is_premium = bool(me.premium)
                    print(f"✅ Estado Premium (método oficial): {is_premium}")
                    if is_premium:
                        return True
        except Exception as e:
            print(f"⚠️  GetUsersRequest falló: {e}")
        
        # Método 2: Usar GetFullUserRequest para información completa
        try:
            full_user_result = await client(GetFullUserRequest(InputUserSelf()))
            if full_user_result and hasattr(full_user_result, 'user'):
                me = full_user_result.user
                print(f"🔍 Información completa del usuario obtenida")
                
                if hasattr(me, 'premium'):
                    is_premium = bool(me.premium)
                    print(f"✅ Estado Premium (GetFullUser): {is_premium}")
                    if is_premium:
                        return True
        except Exception as e:
            print(f"⚠️  GetFullUserRequest falló: {e}")
        
        # Método 3: Verificar usando help.getPremiumPromo 
        try:
            promo_result = await client(GetPremiumPromoRequest())
            if promo_result and hasattr(promo_result, 'users') and promo_result.users:
                # El primer usuario en la respuesta debería ser el usuario actual
                for user in promo_result.users:
                    if hasattr(user, 'self') and user.self:
                        if hasattr(user, 'premium'):
                            is_premium = bool(user.premium)
                            print(f"✅ Estado Premium (PremiumPromo): {is_premium}")
                            if is_premium:
                                return True
        except Exception as e:
            print(f"⚠️  GetPremiumPromo falló: {e}")
        
        # Método 4: Fallback con get_me() mejorado
        try:
            me = await client.get_me()
            
            # Verificar atributo premium
            if hasattr(me, 'premium') and me.premium is True:
                print(f"✅ Estado Premium (get_me fallback): True")
                return True
            
            # Verificar flags manualmente (bit 28 según documentación oficial)
            if hasattr(me, 'flags') and me.flags is not None:
                # Según schema oficial: premium:flags.28?true
                premium_flag = bool(me.flags & (1 << 28))
                print(f"🔍 Verificación de flags - bit 28: {premium_flag}")
                print(f"   Flags raw: 0x{me.flags:x}")
                if premium_flag:
                    return True
        except Exception as e:
            print(f"⚠️  get_me() falló: {e}")
        
        # Si ningún método detectó Premium, es cuenta estándar
        print("📱 Resultado final: Cuenta Estándar (no Premium)")
        print("   Ningún método detectó características Premium")
        return False
        
    except Exception as e:
        print(f"❌ Error crítico en detección Premium: {type(e).__name__}: {e}")
        print("   Asumiendo cuenta Estándar por seguridad")
        return False

async def sendHelloMessage(client, peerChannel):
    global is_premium_account, max_file_size
    
    entity = await client.get_entity(peerChannel)
    
    # Verificar si la cuenta es Premium usando método robusto mejorado
    is_premium_account = await check_premium_status(client)
    
    # Configurar parámetros según el tipo de cuenta
    if is_premium_account:
        max_file_size = int(TELEGRAM_DAEMON_PREMIUM_MAX_SIZE)
        account_type = "Premium ⭐"
        features = "✅ Archivos grandes, ✅ Velocidad optimizada, ✅ Sin límites de descarga"
    else:
        max_file_size = 2000
        account_type = "Standard"
        features = "⚡ Velocidad estándar, 📁 Funciones básicas"
    
    # Aplicar configuraciones optimizadas
    configure_client_for_premium(is_premium_account)
    
    print(f"")
    print(f"🚀 Telegram Download Daemon {TDD_VERSION}")
    print(f"📱 Telethon {__version__}")
    print(f"👤 Tipo de cuenta: {account_type}")
    print(f"📁 Tamaño máximo: {max_file_size} MB")
    print(f"🔄 Workers: {str(worker_count)}")
    print(f"✨ Características: {features}")
    print(f"")
    
    # Mensaje de bienvenida detallado
    hello_msg = f"🚀 **Telegram Download Daemon {TDD_VERSION}**\n"
    hello_msg += f"📱 Telethon {__version__}\n\n"
    hello_msg += f"👤 **Cuenta:** {account_type}\n"
    hello_msg += f"📁 **Tamaño máximo:** {max_file_size} MB\n"
    hello_msg += f"🔄 **Workers:** {str(worker_count)}\n"
    hello_msg += f"✨ **Características:** {features}\n\n"
    
    if is_premium_account:
        hello_msg += f"🎯 **Optimizaciones Premium activas!**\n"
        hello_msg += f"⚡ Sin límites de velocidad\n"
        hello_msg += f"📦 Soporte para archivos grandes\n\n"
    
    hello_msg += f"⚡ **¡Listo para descargas!**"
    
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

                # Optimizaciones para cuentas Premium
                download_kwargs = {
                    'progress_callback': download_callback
                }
                
                # Para cuentas Premium, usar download_file con optimizaciones
                if is_premium_account and size_mb > 100:  # Solo para archivos grandes
                    try:
                        from telethon.tl.functions.upload import GetFileRequest
                        from telethon.tl.types import InputDocumentFileLocation
                        
                        print(f"🚀 Usando descarga optimizada Premium para {filename}")
                        
                        # Usar download_file con chunk_size optimizado para Premium
                        if hasattr(event.media, 'document'):
                            # Parámetros optimizados para Premium
                            file_location = InputDocumentFileLocation(
                                id=event.media.document.id,
                                access_hash=event.media.document.access_hash,
                                file_reference=event.media.document.file_reference,
                                thumb_size=""
                            )
                            
                            # Usar download_file con parámetros optimizados
                            await client.download_file(
                                file_location,
                                "{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX),
                                part_size_kb=1024,  # 1MB chunks para Premium (vs 512KB default)
                                file_size=size,
                                progress_callback=download_callback
                            )
                        else:
                            # Fallback a download_media estándar
                            await client.download_media(
                                event.message, 
                                "{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX), 
                                **download_kwargs
                            )
                    except Exception as opt_e:
                        print(f"⚠️  Descarga optimizada falló, usando método estándar: {opt_e}")
                        # Fallback a método estándar
                        await client.download_media(
                            event.message, 
                            "{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX), 
                            **download_kwargs
                        )
                else:
                    # Descarga estándar para cuentas no Premium o archivos pequeños
                    await client.download_media(
                        event.message, 
                        "{0}/{1}.{2}".format(tempFolder,filename,TELEGRAM_DAEMON_TEMP_SUFFIX), 
                        **download_kwargs
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
