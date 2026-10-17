from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse,JSONResponse
import uvicorn,json,mimetypes
BASE=Path(__file__).resolve().parent
CONTENT=BASE/'content'; MANIFEST=BASE/'manifest.json'
app=FastAPI(title='Pirustudios Launcher Update Server')
@app.get('/manifest.json')
def manifest():
 return JSONResponse(json.loads(MANIFEST.read_text(encoding='utf8')) if MANIFEST.exists() else {'content_version':'0','files':[]})
@app.get('/files/{file_path:path}')
def file(file_path:str):
 root=CONTENT.resolve(); target=(CONTENT/file_path).resolve()
 if (root!=target and root not in target.parents) or not target.is_file():
  raise HTTPException(status_code=404,detail='Archivo no encontrado')
 return FileResponse(target,media_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
if __name__=='__main__':
 uvicorn.run('update_server:app',host='0.0.0.0',port=8000,reload=False)
