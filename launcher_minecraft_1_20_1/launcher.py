import json, os, sys, uuid, hashlib, threading, traceback, subprocess, shutil, re
from pathlib import Path

import requests
import minecraft_launcher_lib
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread, Slot, QLockFile
from PySide6.QtGui import QPixmap, QFont, QIcon
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QProgressBar, QFrame, QHBoxLayout, QDialog, QComboBox, QListWidget, QListWidgetItem, QDialogButtonBox, QTabWidget, QCheckBox, QFormLayout, QSpinBox, QTextEdit)

# Bundled read-only resources (works both from source and PyInstaller).
RESOURCE_BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
BUNDLED_CONFIG = RESOURCE_BASE / 'config.json'
APPDATA = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'PirustudiosLauncher'
APPDATA.mkdir(parents=True, exist_ok=True)
# Prevent two launcher windows from running at once.
LAUNCHER_LOCK = QLockFile(str(APPDATA / 'launcher.lock'))
CONFIG_FILE = APPDATA / 'config.json'
if not CONFIG_FILE.exists():
    shutil.copy2(BUNDLED_CONFIG, CONFIG_FILE)
# Recover automatically if a previous config.json was saved with invalid JSON
# (for example, a Windows path containing unescaped backslashes).
try:
    CONFIG = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
except (json.JSONDecodeError, UnicodeDecodeError):
    try:
        broken = CONFIG_FILE.with_name('config.json.invalid')
        if broken.exists():
            broken = CONFIG_FILE.with_name('config.json.invalid.backup')
        CONFIG_FILE.replace(broken)
    except OSError:
        pass
    shutil.copy2(BUNDLED_CONFIG, CONFIG_FILE)
    CONFIG = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))

MC_VERSION = CONFIG['minecraft_version']
FORGE_VERSION = CONFIG['forge_version']
LAUNCHER_VERSION = CONFIG['launcher_version']
JAVA_RUNTIME = CONFIG.get('java_runtime','java-runtime-gamma')
SERVER = CONFIG.get('server', {})
SERVER_NAME = SERVER.get('name','MI SERVIDOR')
SERVER_ADDRESS = SERVER.get('address','TU-IP-O-DOMINIO')
SERVER_PORT = int(SERVER.get('port',25565))
GAME_DIR = APPDATA / 'game'
GAME_PID_FILE = APPDATA / 'minecraft.pid'

def pid_is_running(pid):
    """Check a Windows PID using tasklist, matching the PID field exactly."""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {int(pid)}', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        line = next((line for line in result.stdout.splitlines() if line.strip().startswith('\"')), '')
        if not line:
            return False
        columns = next(__import__('csv').reader([line]))
        return len(columns) > 1 and columns[1].strip() == str(int(pid))
    except Exception:
        # Fail closed: an uncertain PID is treated as running to avoid a second launch.
        return True


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def same_bundled_file(src, dest):
    # Fast path: shutil.copy2 preserves mtime, so unchanged files need no full hash.
    try:
        a, b = src.stat(), dest.stat()
        if a.st_size != b.st_size:
            return False
        if a.st_mtime_ns == b.st_mtime_ns:
            return True
        if sha256(src) == sha256(dest):
            try:
                os.utime(dest, ns=(a.st_atime_ns, a.st_mtime_ns))
            except OSError:
                pass
            return True
        return False
    except OSError:
        return False


def offline_uuid(name):
    # Match Minecraft Java's stable UUID for offline-mode usernames.
    raw = bytearray(hashlib.md5(('OfflinePlayer:' + name).encode('utf-8')).digest())
    raw[6] = (raw[6] & 0x0f) | 0x30
    raw[8] = (raw[8] & 0x3f) | 0x80
    return str(uuid.UUID(bytes=bytes(raw)))


def safe_join(root, rel):
    root=Path(root).resolve(); target=(root/rel).resolve()
    if root != target and root not in target.parents: raise RuntimeError('Ruta de actualización inválida')
    return target

class Worker(QObject):
    progress=Signal(int,str); finished=Signal(bool,str,bool)
    def __init__(self):
        super().__init__()
        self.force = False

    @Slot()
    def run_update(self):
        force = self.force
        try:
            base=str(CONFIG.get('update_url','')).strip().rstrip('/')
            if not base or 'tu-dominio-o-ip' in base.lower() or not base.lower().startswith('https://'):
                self.finished.emit(True,'up_to_date',False); return
            r=requests.get(base+'/manifest.json',timeout=15); r.raise_for_status(); manifest=r.json()
            local=self.load_local_manifest(); rv=str(manifest.get('content_version','0')); lv=str(local.get('content_version','0'))
            if not force and rv==lv:
                self.finished.emit(True,'up_to_date',False); return
            if not force and rv!=lv:
                # First check only advertises the update. Downloading is started by
                # the player's explicit ACTUALIZAR click, and JUGAR stays locked.
                self.finished.emit(True,'updates_available',False); return
            files=manifest.get('files',[])
            # An empty public manifest is a safe no-op: never erase local mods/packs.
            if not files:
                self.finished.emit(True,'up_to_date',False); return
            wanted=set()
            total=max(1,len(files))
            for i,item in enumerate(files,1):
                rel=item['path'].replace('\\','/')
                if rel.startswith('/') or '..' in Path(rel).parts: raise RuntimeError('Manifest contiene una ruta insegura')
                wanted.add(rel); dest=safe_join(GAME_DIR,rel); dest.parent.mkdir(parents=True,exist_ok=True)
                expected=str(item.get('sha256','')).lower()
                if not re.fullmatch(r'[0-9a-f]{64}', expected): raise RuntimeError('SHA-256 inválido para '+rel)
                ok=dest.exists() and sha256(dest)==expected
                if not ok:
                    self.progress.emit(int((i-1)*100/total),f'Descargando {rel}')
                    file_url=str(item.get('url','')).strip() or (base+'/files/'+rel)
                    if not file_url.lower().startswith('https://'): raise RuntimeError('La URL de descarga debe usar HTTPS: '+rel)
                    rr=requests.get(file_url,timeout=180); rr.raise_for_status()
                    tmp=dest.with_suffix(dest.suffix+'.tmp')
                    try:
                        with open(tmp,'wb') as fh:
                            for chunk in rr.iter_content(chunk_size=1024*1024):
                                if chunk: fh.write(chunk)
                        if sha256(tmp)!=expected: raise RuntimeError('El hash descargado no coincide: '+rel)
                        tmp.replace(dest)
                    finally:
                        try: tmp.unlink(missing_ok=True)
                        except OSError: pass
                self.progress.emit(int(i*100/total),f'Listo: {rel}')
            # Prune only manifest-tracked files when explicitly enabled.
            if manifest.get('remove_missing', False):
                for old in local.get('files',[]):
                    rel=old.get('path','').replace('\\','/')
                    if rel and rel not in wanted:
                        try: safe_join(GAME_DIR,rel).unlink(missing_ok=True)
                        except Exception: pass
            # Also clean legacy pack names that may never have been recorded in the old manifest.
            for old_name in ('resourcepacks/Dedsafio 3.zip',):
                try: safe_join(GAME_DIR,old_name).unlink(missing_ok=True)
                except Exception: pass
            for old_pack in (GAME_DIR/'resourcepacks').glob('*Dedsafio 3 Vanilla*Club Pala*.zip'):
                try: old_pack.unlink(missing_ok=True)
                except OSError: pass
            (GAME_DIR/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
            self.finished.emit(True,'updated',True)
        except Exception as e:
            self.finished.emit(False,str(e),False)
    def load_local_manifest(self):
        p=GAME_DIR/'manifest.json'
        try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        except Exception: return {}

class InstallWorker(QObject):
    progress=Signal(int,str); finished=Signal(bool,str)
    def __init__(self):
        super().__init__()
        self.name = ""

    @Slot()
    def run(self):
        name = self.name
        try:
            GAME_DIR.mkdir(parents=True,exist_ok=True); (GAME_DIR/'mods').mkdir(exist_ok=True); (GAME_DIR/'resourcepacks').mkdir(exist_ok=True)
            # Do NOT delete Morpher here: the online updater installs it in mods/.
            # Older versions removed every *morpher*.jar on every launch.
            # Remove replaced DEDsafio 3 packs from previous installations.
            # The replacement is installed by the online updater as Nutria_DEDsafio2_v1.2.zip.
            for old_pattern in ('Dedsafio 3.zip', '*Dedsafio 3 Vanilla*Club Pala*.zip'):
                for old_pack in (GAME_DIR/'resourcepacks').glob(old_pattern):
                    try: old_pack.unlink()
                    except OSError: pass
            # No eliminar mods existentes: conservar los demás archivos del usuario.
            # Quitar resource packs reemplazados (Cielo rojo apocaliptico -> Revill_Pack).
            for _old in ('Cielo_Rojo_Apocaliptico_CustomSkyboxes_Forge_1.20.1.zip',):
                try: (GAME_DIR/'resourcepacks'/_old).unlink(missing_ok=True)
                except Exception: pass
            # Install bundled mods/resource packs and FancyMenu configuration.
            bundled_content = RESOURCE_BASE / 'content'
            if bundled_content.exists():
                for folder in ('mods', 'resourcepacks'):
                    src_dir = bundled_content / folder
                    dst_dir = GAME_DIR / folder
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    if src_dir.exists():
                        for src in src_dir.iterdir():
                            if src.is_file() and src.suffix.lower() in (('.jar',) if folder == 'mods' else ('.zip',)):
                                # Never reinstall the bundled legacy Dedsafio 3 pack over the replacement.
                                if folder == 'resourcepacks' and (
                                    src.name == 'Dedsafio 3.zip' or
                                    ('Dedsafio 3 Vanilla' in src.name and 'Club Pala' in src.name)
                                ):
                                    continue
                                target = dst_dir / src.name
                                disabled_target = GAME_DIR / ('disabled_' + folder) / src.name
                                # Respect files the player deliberately disabled in Mi pack.
                                if disabled_target.exists():
                                    continue
                                if not same_bundled_file(src, target):
                                    shutil.copy2(src, target)
                src_config = bundled_content / 'config' / 'fancymenu'
                dst_config = GAME_DIR / 'config' / 'fancymenu'
                if src_config.exists():
                    for src in src_config.rglob('*'):
                        if src.is_file():
                            target = dst_config / src.relative_to(src_config)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            if not target.exists() or sha256(target) != sha256(src): shutil.copy2(src, target)
            def status(t): self.progress.emit(-1,str(t))
            def set_progress(v): self.progress.emit(max(0,min(100,int(v))), '')
            cb={'setStatus':status,'setProgress':set_progress,'setMax':lambda m:None}
            # Reutiliza instalaciones existentes; solo descarga componentes que falten.
            self.progress.emit(2,'Comprobando Java 17…')
            java=minecraft_launcher_lib.runtime.get_executable_path(JAVA_RUNTIME,str(GAME_DIR))
            if not java or not Path(java).exists():
                minecraft_launcher_lib.runtime.install_jvm_runtime(JAVA_RUNTIME,str(GAME_DIR),callback=cb)
                java=minecraft_launcher_lib.runtime.get_executable_path(JAVA_RUNTIME,str(GAME_DIR))
            if not java or not Path(java).exists(): raise RuntimeError('No se pudo localizar el Java 17 instalado.')
            self.progress.emit(25,'Comprobando Minecraft 1.20.1…')
            installed_versions=minecraft_launcher_lib.utils.get_installed_versions(str(GAME_DIR))
            installed_ids={v.get('id','') for v in installed_versions}
            if MC_VERSION not in installed_ids:
                minecraft_launcher_lib.install.install_minecraft_version(MC_VERSION,str(GAME_DIR),callback=cb)
            self.progress.emit(65,f'Comprobando Forge {FORGE_VERSION}…')
            forge_id=f'{MC_VERSION}-forge-{FORGE_VERSION}'
            installed_versions=minecraft_launcher_lib.utils.get_installed_versions(str(GAME_DIR))
            launch_id=next((v['id'] for v in installed_versions if 'forge' in v.get('id','').lower() and FORGE_VERSION in v.get('id','')),None)
            if not launch_id:
                versions=minecraft_launcher_lib.forge.list_forge_versions()
                candidate=forge_id if forge_id in versions else next((v for v in versions if v.endswith('-'+FORGE_VERSION) or v==FORGE_VERSION),None)
                if not candidate: raise RuntimeError(f'Forge {FORGE_VERSION} no está disponible para instalación automática.')
                minecraft_launcher_lib.forge.install_forge_version(candidate,str(GAME_DIR),callback=cb,java=java)
                installed_versions=minecraft_launcher_lib.utils.get_installed_versions(str(GAME_DIR))
                launch_id=next((v['id'] for v in installed_versions if 'forge' in v.get('id','').lower() and FORGE_VERSION in v.get('id','')),candidate)
            self.progress.emit(92,'Preparando el servidor…')
            # Conservative Java 17 garbage-collector settings for a Forge 1.20.1 client.
            # Respect the user's RAM preference, but avoid accidental extreme heap values.
            ram_mb = max(2048, min(12288, int(CONFIG.get('ram_max_mb', 6144))))
            jvm_args = [
                f'-Xms{min(2048, ram_mb)}M',
                f'-Xmx{ram_mb}M',
                '-XX:+UseG1GC',
                '-XX:+ParallelRefProcEnabled',
                '-XX:MaxGCPauseMillis=200',
                '-XX:+DisableExplicitGC',
                '-XX:G1ReservePercent=20',
                '-XX:G1HeapRegionSize=16M',
            ]
            options={'username':name,'uuid':offline_uuid(name),'token':'','launcherName':'PirustudiosLauncher','launcherVersion':LAUNCHER_VERSION,'executablePath':java,'defaultExecutablePath':java,'gameDirectory':str(GAME_DIR),'jvmArguments':jvm_args}
            command=minecraft_launcher_lib.command.get_minecraft_command(launch_id,str(GAME_DIR),options)
            # Keep existing player settings untouched. Set moderate performance defaults only
            # for a fresh profile, before enabling installed resource packs.
            options_file = GAME_DIR / 'options.txt'
            if not options_file.exists():
                default_options = [
                    'renderDistance:10',
                    'simulationDistance:6',
                    'graphics:fast',
                    'particles:2',
                    'entityDistanceScaling:0.75',
                    'biomeBlendRadius:2',
                    'maxFps:120',
                    'enableVsync:false',
                    'clouds:fast',
                    'mipmapLevels:2',
                    'ao:true',
                ]
                options_file.write_text('\\n'.join(default_options) + '\\n', encoding='utf-8')
            pack_names = [p.name for p in sorted((GAME_DIR/'resourcepacks').glob('*.zip'))]
            if pack_names:
                try:
                    lines = options_file.read_text(encoding='utf-8').splitlines() if options_file.exists() else []
                    found = False
                    for i, line in enumerate(lines):
                        if line.startswith('resourcePacks:'):
                            found = True
                            # Migrate this launcher's old bare filenames to Minecraft's file/ identifiers,
                            # while preserving the player's selected packs and order.
                            try:
                                selected = json.loads(line[len('resourcePacks:'):])
                                known = set(pack_names)
                                old_ids = {
                                    'Dedsafio 3.zip', 'file/Dedsafio 3.zip',
                                }
                                selected = [item for item in selected if item not in old_ids and not (
                                    'Dedsafio 3 Vanilla' in item and 'Club Pala' in item
                                )]
                                selected = [('file/' + item if item in known else item) for item in selected]
                                replacement = 'file/Nutria_DEDsafio2_v1.2.zip'
                                if 'Nutria_DEDsafio2_v1.2.zip' in known and replacement not in selected:
                                    selected.append(replacement)
                                if not selected:
                                    selected = ['vanilla'] + ['file/' + n for n in pack_names] + ['mod_resources']
                                lines[i] = 'resourcePacks:' + json.dumps(selected, ensure_ascii=False, separators=(',', ':'))
                            except (ValueError, TypeError):
                                pass
                            break
                    if not found:
                        selected = ['vanilla'] + ['file/' + n for n in pack_names] + ['mod_resources']
                        lines.append('resourcePacks:' + json.dumps(selected, ensure_ascii=False, separators=(',', ':')))
                    if not any(line.startswith('incompatibleResourcePacks:') for line in lines):
                        lines.append('incompatibleResourcePacks:[]')
                    options_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                except OSError:
                    pass
            # Start Minecraft and connect to the configured server.
            self.progress.emit(100, 'Todo listo. Abriendo Minecraft…')
            log_path = APPDATA / 'minecraft-launch.log'
            with open(log_path, 'w', encoding='utf-8', errors='replace') as log:
                log.write('Launching Minecraft/Forge\\n')
                log.write(f'Minecraft: {MC_VERSION} | Forge: {FORGE_VERSION}\\n')
                log.write(f'Java: {java}\\n')
                log.write('Command: ' + subprocess.list2cmdline(command) + '\\n\\n')
                log.flush()
                proc = subprocess.Popen(
                    command, cwd=str(GAME_DIR),
                    stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
            self.finished.emit(True, f'started|pid={proc.pid}|log={log_path}')
        except Exception: self.finished.emit(False,traceback.format_exc())

class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.game_process = None
        self.game_pid = None
        self.launch_in_progress = False
        self.game_watch = QTimer(self)
        self.game_watch.setInterval(2500)
        self.game_watch.timeout.connect(self.check_game_process)
        self.setWindowTitle(f'PeriSafio Launcher — Minecraft {MC_VERSION} Forge')
        self.resize(1440, 850)
        self.setMinimumSize(1120, 720)
        icon=RESOURCE_BASE/'assets'/'launcher.ico'
        if icon.exists(): self.setWindowIcon(QIcon(str(icon)))
        self.setStyleSheet("""
            QWidget { color:#edf1f8; font-family:'Segoe UI'; background:#0a0d13; }
            QLabel { background:transparent; }
            QLineEdit { background:#1a202b; border:1px solid #303746; border-radius:7px; padding:11px; color:#fff; font-size:13px; }
            QLineEdit:focus { border:1px solid #f3b642; }
            QPushButton { background:#f2b544; color:#17120a; border:0; border-radius:8px; padding:12px; font-weight:800; font-size:13px; }
            QPushButton:hover { background:#ffd071; }
            QPushButton:disabled { background:#544638; color:#a99f94; }
            QProgressBar { border:0; border-radius:4px; background:#171d27; height:8px; text-align:center; }
            QProgressBar::chunk { background:#eaa52e; border-radius:4px; }
        """)
        self.build_ui()
        self.restore_game_process()
        self.check_for_updates()
        self.timer=QTimer(self); self.timer.timeout.connect(self.check_for_updates)
        if self.has_update_url(): self.timer.start(max(60,int(CONFIG.get('poll_seconds',60))*1000))

    def has_update_url(self):
        base=str(CONFIG.get('update_url','')).strip().rstrip('/')
        return bool(base and base.lower().startswith('https://') and 'tu-dominio-o-ip' not in base.lower())

    def build_ui(self):
        root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        sidebar=QFrame(); sidebar.setFixedWidth(190); sidebar.setStyleSheet('QFrame{background:#0e121a;border-right:1px solid #252b36;}')
        sl=QVBoxLayout(sidebar); sl.setContentsMargins(18,24,16,20); sl.setSpacing(12)
        brand=QLabel('🟨  PERISAFIO'); brand.setStyleSheet('font-size:17px;font-weight:900;color:#f5bd4d;letter-spacing:1px;'); sl.addWidget(brand)
        subbrand=QLabel('      LAUNCHER'); subbrand.setStyleSheet('font-size:9px;color:#71829c;letter-spacing:2px;'); sl.addWidget(subbrand)
        sl.addSpacing(24)
        season=QLabel('TEMPORADA  01'); season.setStyleSheet('font-size:9px;color:#71829c;letter-spacing:2px;'); sl.addWidget(season)
        nav_style='QPushButton{text-align:left;padding:10px;color:#9ba8bc;background:transparent;border:1px solid transparent;border-radius:7px;font-size:12px;} QPushButton:hover{background:#1a202b;color:#f5bd4d;border:1px solid #303746;}'
        home_btn=QPushButton('⌂   Inicio'); home_btn.setStyleSheet(nav_style); home_btn.clicked.connect(lambda: self.status.setText('Inicio · PeriSafio listo para jugar')); sl.addWidget(home_btn)
        pack_btn=QPushButton('⬡   Mi pack'); pack_btn.setStyleSheet(nav_style); pack_btn.clicked.connect(self.open_pack); sl.addWidget(pack_btn)
        news_btn=QPushButton('▤   Novedades'); news_btn.setStyleSheet(nav_style); news_btn.clicked.connect(self.open_news); sl.addWidget(news_btn)
        sl.addStretch()
        serverdot=QLabel('●  Servidor configurado'); serverdot.setStyleSheet('color:#4bd6a0;font-size:10px;'); sl.addWidget(serverdot)
        sl.addSpacing(12)
        prefs_btn=QPushButton('⚙   Preferencias'); prefs_btn.setStyleSheet(nav_style); prefs_btn.clicked.connect(self.open_preferences); sl.addWidget(prefs_btn)
        footer=QLabel('PERISAFIO NETWORK  •  BETA'); footer.setStyleSheet('font-size:8px;color:#64728a;'); sl.addWidget(footer)
        root.addWidget(sidebar)

        main=QWidget(); ml=QVBoxLayout(main); ml.setContentsMargins(34,22,34,24); ml.setSpacing(16)
        top=QHBoxLayout(); crumb=QLabel('PERISAFIO   /   INICIO'); crumb.setStyleSheet('font-size:10px;color:#f3b642;letter-spacing:2px;'); top.addWidget(crumb); top.addStretch()
        self.logged_user=QLabel(); self.logged_user.setStyleSheet('font-size:10px;color:#f3c45e;border:1px solid #393224;border-radius:6px;padding:8px;'); self.refresh_logged_user(); top.addWidget(self.logged_user)
        online=QLabel('●  Servidor configurado   |   Minecraft 1.20.1'); online.setStyleSheet('font-size:10px;color:#75d7ad;border:1px solid #263b3a;border-radius:6px;padding:8px;'); top.addWidget(online); ml.addLayout(top)
        hero=QFrame(); hero.setStyleSheet('QFrame{background:#0d1119;border:1px solid #222a36;border-radius:12px;}')
        hl=QHBoxLayout(hero); hl.setContentsMargins(26,22,26,22)
        left=QVBoxLayout(); kicker=QLabel('—  EL DESAFÍO COMIENZA AQUÍ'); kicker.setStyleSheet('font-size:10px;color:#f3b642;font-weight:800;letter-spacing:2px;'); left.addWidget(kicker)
        heading=QLabel('Tu próxima\naventura empieza.'); heading.setFont(QFont('Segoe UI',27,QFont.Weight.Bold)); heading.setStyleSheet('color:#f4f5f8;'); left.addWidget(heading)
        desc=QLabel('Todo lo que necesitas para entrar a PeriSafio.\nSin pasos extra. Sin otros launchers.'); desc.setStyleSheet('font-size:12px;color:#8997ad;'); left.addWidget(desc)
        self.status=QLabel('Preparando el launcher…'); self.status.setWordWrap(True); self.status.setStyleSheet('font-size:11px;color:#91a0b8;'); left.addWidget(self.status)
        hl.addLayout(left,1)
        logo=QLabel(); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); logo.setFixedSize(300,170)
        logo_path=RESOURCE_BASE/'assets'/'perisafio_logo.png'
        if logo_path.exists(): logo.setPixmap(QPixmap(str(logo_path)).scaled(290,165,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        else: logo.setText('PERISAFIO'); logo.setStyleSheet('color:#f4b642;font-size:22px;font-weight:900;')
        hl.addWidget(logo)
        ml.addWidget(hero)

        cards=QHBoxLayout(); cards.setSpacing(14)
        access=QFrame(); access.setStyleSheet('QFrame{background:#111620;border:1px solid #29313e;border-radius:10px;}'); al=QVBoxLayout(access); al.setContentsMargins(18,18,18,18); al.setSpacing(10)
        label=QLabel('01  /  ACCESO'); label.setStyleSheet('font-size:9px;color:#8295b2;letter-spacing:2px;'); al.addWidget(label)
        at=QLabel('Listo para jugar'); at.setFont(QFont('Segoe UI',16,QFont.Weight.Bold)); al.addWidget(at)
        atsub=QLabel('Tu nombre se guardará para la próxima vez.'); atsub.setStyleSheet('font-size:11px;color:#8d9bb0;'); al.addWidget(atsub)
        userlabel=QLabel('Nombre de jugador'); userlabel.setStyleSheet('font-size:10px;font-weight:700;'); al.addWidget(userlabel)
        self.username=QLineEdit(); self.username.setPlaceholderText('Tu nombre en Minecraft'); self.username.setText(str(CONFIG.get('last_username',''))); self.username.textChanged.connect(self.save_username); al.addWidget(self.username)
        serverlabel=QLabel('SERVIDOR'); serverlabel.setStyleSheet('font-size:9px;color:#8295b2;letter-spacing:1px;'); al.addWidget(serverlabel)
        addr=QLabel(f'{SERVER_ADDRESS}:{SERVER_PORT}'); addr.setStyleSheet('font-family:Consolas;font-size:12px;color:#f4c15e;'); al.addWidget(addr)
        self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.hide(); al.addWidget(self.progress)
        self.play_btn=QPushButton('▶     JUGAR'); self.play_btn.clicked.connect(self.play); self.play_btn.setMinimumHeight(48); al.addWidget(self.play_btn)
        self.update_btn=QPushButton('↻     ACTUALIZAR'); self.update_btn.clicked.connect(lambda:self.check_for_updates(force=True)); self.update_btn.hide(); al.addWidget(self.update_btn)
        al.addStretch()
        note=QLabel(f'Minecraft {MC_VERSION}  •  Forge {FORGE_VERSION}  •  Java 17'); note.setStyleSheet('font-size:10px;color:#71829c;'); al.addWidget(note)
        cards.addWidget(access,1)

        sync=QFrame(); sync.setStyleSheet('QFrame{background:#111620;border:1px solid #29313e;border-radius:10px;}'); rl=QVBoxLayout(sync); rl.setContentsMargins(18,18,18,18); rl.setSpacing(13)
        rlabel=QLabel('02  /  SINCRONIZACIÓN'); rlabel.setStyleSheet('font-size:9px;color:#8295b2;letter-spacing:2px;'); rl.addWidget(rlabel)
        rt=QLabel('Tu pack, siempre al día.'); rt.setFont(QFont('Segoe UI',16,QFont.Weight.Bold)); rl.addWidget(rt)
        rsub=QLabel('Java, Forge, mods y resource packs se conservan entre sesiones.'); rsub.setWordWrap(True); rsub.setStyleSheet('font-size:11px;color:#8d9bb0;'); rl.addWidget(rsub)
        for title,detail in [('Forge 1.20.1',f'Versión {FORGE_VERSION}'),('Mods del servidor','Se comprueban al iniciar'),('Resource packs','Se conservan en tu instalación')]:
            row=QFrame(); row.setStyleSheet('QFrame{background:#171d28;border:1px solid #2b3340;border-radius:7px;}'); rowl=QVBoxLayout(row); rowl.setContentsMargins(12,9,12,9); rowl.setSpacing(3)
            ttl=QLabel('✓   '+title); ttl.setStyleSheet('font-size:11px;font-weight:700;color:#e8edf6;'); rowl.addWidget(ttl)
            det=QLabel(detail); det.setStyleSheet('font-size:9px;color:#8292a9;'); rowl.addWidget(det); rl.addWidget(row)
        rl.addStretch()
        safety=QLabel('Instala las actualizaciones disponibles antes de jugar. Si una actualización falla, vuelve a pulsar ACTUALIZAR para intentarlo de nuevo.'); safety.setWordWrap(True); safety.setStyleSheet('font-size:10px;color:#8c9ab0;background:#171d28;border:1px solid #2b3340;border-radius:7px;padding:10px;'); rl.addWidget(safety)
        cards.addWidget(sync,1); ml.addLayout(cards,1)
        root.addWidget(main,1)

    def refresh_logged_user(self):
        name=str(CONFIG.get('last_username','')).strip()
        self.logged_user.setText(f'●  Sesión guardada: {name}' if name else 'Invitado · inicia una vez')

    def open_preferences(self):
        dlg=QDialog(self); dlg.setWindowTitle('Preferencias de PeriSafio'); dlg.resize(440,260)
        dlg.setStyleSheet("QDialog{background:#0e121a;color:#edf1f8;} QLabel{color:#edf1f8;} QComboBox{background:#1a202b;color:#fff;padding:8px;border:1px solid #303746;border-radius:6px;} QPushButton{background:#f2b544;color:#17120a;padding:9px;border-radius:6px;font-weight:700;}")
        layout=QVBoxLayout(dlg); title=QLabel('Preferencias'); title.setStyleSheet('font-size:20px;font-weight:800;color:#f3b642;'); layout.addWidget(title)
        form=QFormLayout(); ram=QComboBox()
        choices=[('2 GB',2048),('3 GB',3072),('4 GB',4096),('5 GB',5120),('6 GB',6144),('8 GB',8192),('10 GB',10240),('12 GB',12288)]
        for label,mb in choices: ram.addItem(label,mb)
        current=int(CONFIG.get('ram_max_mb',6144)); idx=next((i for i,(_,mb) in enumerate(choices) if mb==current),4); ram.setCurrentIndex(idx)
        form.addRow('Memoria RAM para Minecraft:',ram); layout.addLayout(form)
        hint=QLabel('Elige según la memoria de tu PC. Se aplicará en el próximo inicio del juego.'); hint.setWordWrap(True); hint.setStyleSheet('color:#93a1b7;font-size:11px;'); layout.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); layout.addWidget(buttons)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            CONFIG['ram_max_mb']=int(ram.currentData()); CONFIG['ram_min_mb']=min(2048,int(CONFIG['ram_max_mb']))
            self.persist_config(); self.status.setText(f'Preferencias guardadas · RAM: {ram.currentText()}')

    def open_news(self):
        dlg=QDialog(self); dlg.setWindowTitle('Novedades de PeriSafio'); dlg.resize(520,360)
        dlg.setStyleSheet("QDialog{background:#0e121a;color:#edf1f8;} QLabel{color:#edf1f8;} QTextEdit{background:#151b25;color:#dbe4f3;border:1px solid #303746;border-radius:7px;padding:10px;} QPushButton{background:#f2b544;color:#17120a;padding:9px;border-radius:6px;font-weight:700;}")
        layout=QVBoxLayout(dlg); title=QLabel('Novedades'); title.setStyleSheet('font-size:20px;font-weight:800;color:#f3b642;'); layout.addWidget(title)
        text=QTextEdit(); text.setReadOnly(True); text.setText(f'PERISAFIO · Minecraft {MC_VERSION} · Forge {FORGE_VERSION}\n\n• Launcher con nombre de jugador guardado.\n• Selección de memoria RAM.\n• Administración local de mods y resource packs.\n• FancyMenu y su configuración personalizada.\n• Las actualizaciones online son opcionales hasta configurar un servidor HTTPS.'); layout.addWidget(text)
        close=QPushButton('Cerrar'); close.clicked.connect(dlg.accept); layout.addWidget(close); dlg.exec()

    def open_pack(self):
        dlg=QDialog(self); dlg.setWindowTitle('Mi pack · PeriSafio'); dlg.resize(650,520)
        dlg.setStyleSheet("QDialog{background:#0e121a;color:#edf1f8;} QLabel{color:#edf1f8;} QListWidget{background:#151b25;color:#dbe4f3;border:1px solid #303746;border-radius:7px;} QPushButton{background:#f2b544;color:#17120a;padding:9px;border-radius:6px;font-weight:700;} QTabWidget::pane{border:1px solid #303746;}")
        layout=QVBoxLayout(dlg); title=QLabel('Mi pack'); title.setStyleSheet('font-size:20px;font-weight:800;color:#f3b642;'); layout.addWidget(title)
        tabs=QTabWidget(); lists={}
        for key,folder,ext in [('Mods',GAME_DIR/'mods','.jar'),('Resource packs',GAME_DIR/'resourcepacks','.zip')]:
            page=QWidget(); v=QVBoxLayout(page); hint=QLabel('Marca los archivos que quieras mantener activos. Los cambios se aplican al próximo inicio.'); hint.setWordWrap(True); hint.setStyleSheet('color:#93a1b7;font-size:11px;'); v.addWidget(hint)
            lst=QListWidget(); lst.setSelectionMode(QListWidget.SelectionMode.NoSelection); lists[key]=(lst,folder,ext)
            enabled=folder; disabled=GAME_DIR/('disabled_'+folder.name); enabled.mkdir(parents=True,exist_ok=True); disabled.mkdir(parents=True,exist_ok=True)
            for f in sorted(list(enabled.glob('*'+ext))+list(disabled.glob('*'+ext))):
                item=QListWidgetItem(f.name); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked if f.parent==enabled else Qt.CheckState.Unchecked); item.setData(Qt.ItemDataRole.UserRole,str(f)); lst.addItem(item)
            v.addWidget(lst); tabs.addTab(page,key)
        layout.addWidget(tabs)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); layout.addWidget(buttons)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            for lst,enabled,ext in lists.values():
                disabled=GAME_DIR/('disabled_'+enabled.name); enabled.mkdir(parents=True,exist_ok=True); disabled.mkdir(parents=True,exist_ok=True)
                for i in range(lst.count()):
                    item=lst.item(i); src=Path(item.data(Qt.ItemDataRole.UserRole)); target_dir=enabled if item.checkState()==Qt.CheckState.Checked else disabled
                    target=target_dir/src.name
                    if src.exists() and src.parent!=target_dir:
                        target_dir.mkdir(parents=True,exist_ok=True)
                        if target.exists(): target.unlink()
                        shutil.move(str(src),str(target))
            # Select only checked resource packs in Minecraft options.txt.
            try:
                active=['vanilla'] + ['file/' + p.name for p in sorted((GAME_DIR/'resourcepacks').glob('*.zip'))] + ['mod_resources']
                opt=GAME_DIR/'options.txt'; lines=opt.read_text(encoding='utf-8').splitlines() if opt.exists() else []
                encoded=json.dumps(active,ensure_ascii=False,separators=(',',':')); found=False
                for i,line in enumerate(lines):
                    if line.startswith('resourcePacks:'): lines[i]='resourcePacks:'+encoded; found=True; break
                if not found: lines.append('resourcePacks:'+encoded)
                if not any(x.startswith('incompatibleResourcePacks:') for x in lines): lines.append('incompatibleResourcePacks:[]')
                opt.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            except OSError: pass
            self.status.setText('Mi pack guardado. Los cambios se aplicarán al próximo inicio de Minecraft.')

    def persist_config(self):
        try:
            tmp=CONFIG_FILE.with_suffix('.tmp'); tmp.write_text(json.dumps(CONFIG,indent=2,ensure_ascii=False),encoding='utf-8'); tmp.replace(CONFIG_FILE)
        except OSError: pass

    def save_username(self, value):
        CONFIG['last_username']=value.strip()
        self.persist_config()
        if hasattr(self,'logged_user'): self.refresh_logged_user()

    def check_for_updates(self,force=False):
        if not self.has_update_url():
            self.status.setText('✓ Launcher listo. El contenido instalado se conservará; las actualizaciones online no están configuradas.')
            running = self.is_game_running()
            self.play_btn.setEnabled(not running)
            self.update_btn.hide()
            if running:
                self.update_btn.setEnabled(False)
            return
        self.status.setText('Comprobando y aplicando actualizaciones…'); self.update_btn.setText('↻     ACTUALIZAR'); self.update_btn.hide(); self.play_btn.setEnabled(False)
        worker=Worker(); worker.force=force
        thread=QThread(); worker.moveToThread(thread)
        thread.started.connect(worker.run_update)
        worker.progress.connect(self.on_progress)
        worker.finished.connect(lambda ok,msg,has:self.on_update_finished(ok,msg,has,thread))
        thread.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
        thread.start(); self.thread=thread; self.worker=worker

    def on_progress(self,p,text):
        self.progress.show()
        if p>=0:self.progress.setValue(p)
        if text:self.status.setText(text)

    def on_update_finished(self,ok,msg,has,thread):
        self.progress.hide()
        running = self.is_game_running()
        if running:
            self.play_btn.setEnabled(False)
            self.update_btn.setEnabled(False)
            self.update_btn.hide()
            self.status.setText('Minecraft está abierto. Cierra el juego antes de actualizar o volver a jugar.')
        elif ok and msg=='updates_available':
            # Update detected, but not installed yet: require explicit action.
            self.update_btn.setText('↻     ACTUALIZAR')
            self.update_btn.show()
            self.update_btn.setEnabled(True)
            self.play_btn.setEnabled(False)
            self.status.setText('Hay contenido nuevo disponible. Pulsa ACTUALIZAR para instalarlo; JUGAR está bloqueado hasta terminar.')
        elif ok:
            # A successful check/update ends the action: hide the button so it cannot
            # confuse players or be clicked repeatedly. Jugar unlocks only after success.
            self.update_btn.hide()
            self.update_btn.setEnabled(True)
            self.play_btn.setEnabled(True)
            if msg=='up_to_date': self.status.setText('✓ Todo está actualizado. Ya puedes jugar.')
            else: self.status.setText('✓ Actualización completada. Ya puedes jugar.')
        else:
            # Fail closed: never let the player launch with a failed/incomplete update.
            self.update_btn.setText('↻     REINTENTAR ACTUALIZACIÓN')
            self.update_btn.show()
            self.update_btn.setEnabled(True)
            self.play_btn.setEnabled(False)
            self.status.setText('No se pudo completar la actualización. Pulsa REINTENTAR ACTUALIZACIÓN; JUGAR seguirá bloqueado hasta que termine correctamente.')
        thread.quit()

    def play(self):
        if self.launch_in_progress or self.is_game_running():
            self.play_btn.setEnabled(False)
            self.update_btn.setEnabled(False)
            self.status.setText('Minecraft ya está abierto o iniciándose. Cierra el juego antes de volver a pulsar Jugar.')
            return
        name=self.username.text().strip()
        if not name: QMessageBox.warning(self,'Falta el usuario','Escribe tu nombre una sola vez; lo guardaremos para la próxima.'); return
        if not re.fullmatch(r'[A-Za-z0-9_]{3,16}', name): QMessageBox.warning(self,'Nombre inválido','Usa entre 3 y 16 caracteres: letras, números o guion bajo.'); return
        self.save_username(name)
        self.launch_in_progress = True
        self.play_btn.setEnabled(False); self.update_btn.setEnabled(False); self.progress.show(); self.progress.setValue(0); self.status.setText('Comprobando instalación; solo se descargará lo que falte…')
        self.install_worker=InstallWorker(); self.install_worker.name=name
        self.install_thread=QThread(); self.install_worker.moveToThread(self.install_thread)
        self.install_thread.started.connect(self.install_worker.run)
        self.install_worker.progress.connect(self.on_install_progress)
        self.install_worker.finished.connect(self.on_install_finished)
        self.install_thread.finished.connect(self.install_worker.deleteLater)
        self.install_thread.finished.connect(self.install_thread.deleteLater)
        self.install_thread.start()

    def on_install_progress(self,v,text):
        if v>=0:self.progress.setValue(v)
        if text:self.status.setText(text)

    def on_install_finished(self,ok,msg):
        self.progress.hide()
        self.launch_in_progress = False
        if ok:
            # Worker returns a stable PID for the Minecraft Java process.
            match = re.search(r'started\|pid=(\d+)\|log=(.+)', msg)
            if match:
                pid = int(match.group(1))
                self.game_pid = pid
                try:
                    GAME_PID_FILE.write_text(str(pid), encoding='ascii')
                except OSError:
                    pass
                self.play_btn.setEnabled(False)
                self.update_btn.setEnabled(False)
                self.status.setText('✓ Minecraft se abrió. Jugar y actualizar estarán bloqueados hasta que cierres el juego.')
                self.game_watch.start()
            else:
                # The process was started but could not be tracked: fail safe and do not
                # enable another launch in this window.
                self.play_btn.setEnabled(False)
                self.update_btn.setEnabled(False)
                self.status.setText('Minecraft se está iniciando, pero no pude confirmar su PID. Reinicia el launcher solo después de cerrar el juego.')
            self.install_thread.quit()
            return
        self.play_btn.setEnabled(not self.is_game_running())
        self.update_btn.setEnabled(not self.is_game_running())
        self.status.setText('No se pudo iniciar Minecraft. Revisa el registro si persiste.')
        QMessageBox.critical(self,'No se pudo iniciar',msg)
        self.install_thread.quit()

    def restore_game_process(self):
        """Keep Jugar locked if Minecraft survived a launcher restart."""
        try:
            raw = GAME_PID_FILE.read_text(encoding='ascii').strip()
            pid = int(raw)
        except (OSError, ValueError):
            self.game_pid = None
            return
        if pid_is_running(pid):
            self.game_pid = pid
            self.play_btn.setEnabled(False)
            self.update_btn.setEnabled(False)
            self.status.setText('Minecraft sigue abierto. Cierra el juego antes de iniciar otra instancia.')
            self.game_watch.start()
        else:
            self.game_pid = None
            try:
                GAME_PID_FILE.unlink(missing_ok=True)
            except OSError:
                pass

    def is_game_running(self):
        pid = getattr(self, 'game_pid', None)
        if pid is None:
            return False
        if pid_is_running(pid):
            return True
        self.game_pid = None
        try:
            GAME_PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return False

    def check_game_process(self):
        pid = getattr(self, 'game_pid', None)
        if pid is None:
            self.game_watch.stop()
            return
        if not pid_is_running(pid):
            self.game_watch.stop()
            self.game_pid = None
            self.game_process = None
            try:
                GAME_PID_FILE.unlink(missing_ok=True)
            except OSError:
                pass
            self.play_btn.setEnabled(True)
            self.update_btn.setEnabled(True)
            self.status.setText('Minecraft se cerró. Ya puedes volver a pulsar Jugar.')

if __name__=='__main__':
    app=QApplication(sys.argv)
    if not LAUNCHER_LOCK.tryLock(100):
        QMessageBox.information(None, 'PeriSafio ya está abierto', 'El launcher ya está ejecutándose. Revisa la ventana abierta para evitar iniciar varias copias.')
        sys.exit(0)
    w=Launcher(); w.show(); sys.exit(app.exec())
