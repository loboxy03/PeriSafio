import sys,json,hashlib,shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QPushButton,QLabel,QFileDialog,QMessageBox,QInputDialog
BASE=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
CONTENT=BASE/'content'; MODS=CONTENT/'mods'; PACKS=CONTENT/'resourcepacks'; MANIFEST=BASE/'manifest.json'; CONFIG=BASE/'config.json'
for p in (MODS,PACKS): p.mkdir(parents=True,exist_ok=True)
def sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()
def load_config(): return json.loads(CONFIG.read_text(encoding='utf8'))
def save_config(c): CONFIG.write_text(json.dumps(c,indent=2,ensure_ascii=False),encoding='utf8')
def publish():
 old={}
 if MANIFEST.exists():
  try: old=json.loads(MANIFEST.read_text(encoding='utf8'))
  except (ValueError,OSError): pass
 v=int(old.get('content_version',0))+1; files=[]
 for root,kind in ((MODS,'mod'),(PACKS,'resourcepack')):
  for p in sorted(root.iterdir()):
   if p.is_file(): files.append({'path':str(p.relative_to(CONTENT)).replace('\\','/'),'type':kind,'size':p.stat().st_size,'sha256':sha256(p)})
 MANIFEST.write_text(json.dumps({'content_version':str(v),'files':files},indent=2,ensure_ascii=False),encoding='utf8')
 return v,len(files)
class Admin(QWidget):
 def __init__(self):
  super().__init__(); self.setWindowTitle('Pirustudios Launcher — Administrador'); self.resize(560,480)
  self.setStyleSheet('QWidget{background:#100c15;color:white;font-family:Segoe UI;} QPushButton{background:#eaa52e;color:#21150c;border:0;border-radius:8px;padding:12px;font-weight:800;} QPushButton:hover{background:#ffc15a;}')
  l=QVBoxLayout(self); l.setContentsMargins(35,35,35,35); l.setSpacing(12); l.addWidget(QLabel('<h2>ADMINISTRADOR</h2>')); l.addWidget(QLabel('Este panel controla el servidor y el contenido que reciben los jugadores.'))
  for title,fn in [('CONFIGURAR ÚNICO SERVIDOR',self.server),('CONFIGURAR URL DE ACTUALIZACIONES (HTTPS)',self.update_url),('＋ AGREGAR MODS (.JAR)',lambda:self.add('mod')),('＋ AGREGAR RESOURCE PACKS (.ZIP)',lambda:self.add('pack')),('PUBLICAR ACTUALIZACIÓN',self.publish)]:
   b=QPushButton(title); b.clicked.connect(fn); l.addWidget(b)
  self.info=QLabel('Sin cambios publicados.'); self.info.setWordWrap(True); l.addWidget(self.info)
 def server(self):
  c=load_config(); s=c.setdefault('server',{})
  name,ok=QInputDialog.getText(self,'Servidor','Nombre del servidor:',text=s.get('name','MI SERVIDOR'))
  if not ok:return
  addr,ok=QInputDialog.getText(self,'Servidor','IP o dominio:',text=s.get('address','TU-IP-O-DOMINIO'))
  if not ok:return
  port,ok=QInputDialog.getInt(self,'Servidor','Puerto:',int(s.get('port',25565)),1,65535)
  if not ok:return
  s.update({'name':name,'address':addr,'port':port}); save_config(c); self.info.setText(f'✓ Servidor configurado: {name} — {addr}:{port}')
 def update_url(self):
  c=load_config()
  url,ok=QInputDialog.getText(self,'Actualizaciones','URL HTTPS pública para manifest.json y /files/:',text=c.get('update_url',''))
  if not ok:return
  url=url.strip().rstrip('/')
  if url and not url.startswith('https://'):
   QMessageBox.warning(self,'URL no segura','Usa una URL HTTPS pública.'); return
  c['update_url']=url; save_config(c); self.info.setText('✓ URL: '+(url if url else 'actualizaciones remotas desactivadas'))
 def add(self,kind):
  files,_=QFileDialog.getOpenFileNames(self,'Seleccionar archivos')
  if not files:return
  dest=MODS if kind=='mod' else PACKS
  for f in files:
   src=Path(f)
   if kind=='mod' and src.suffix.lower()!='.jar':continue
   if kind=='pack' and src.suffix.lower()!='.zip':continue
   shutil.copy2(src,dest/src.name)
  self.info.setText(f'Archivos copiados a {dest}. Pulsa PUBLICAR ACTUALIZACIÓN.')
 def publish(self):
  v,n=publish(); self.info.setText(f'✓ Publicado contenido {v} — {n} archivos.')
  QMessageBox.information(self,'Publicado',f'Actualización {v} lista. Los jugadores verán ACTUALIZAR.')
if __name__=='__main__':
 app=QApplication(sys.argv); w=Admin(); w.show(); sys.exit(app.exec())
