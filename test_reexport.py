"""Reexport a completed job; automatic fallback and retry after encoder failure."""
import os,tempfile,time,json
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-reexport-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
 for _ in range(200):
  d=c.get('/api/jobs/'+j).json()
  if d['status'] in ['done','review','error']:return d
  time.sleep(.1)
 raise AssertionError('timeout')

def main():
 source=app.DATA/'source.mp4'
 app.ff(['-f','lavfi','-i','testsrc2=s=180x320:r=30:d=4','-f','lavfi','-i','sine=frequency=440:duration=4','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
 real=app.run
 def fixture(args,timeout=1800):
  if len(args)>1 and args[1].endswith('transcribe_task.py'):return json.dumps([{'start':.3,'end':1.5,'text':'Uma frase comum sobre o cotidiano.'},{'start':2,'end':3,'text':'Outra frase segue tranquila.'}]),''
  return real(args,timeout)
 app.run=fixture
 with TestClient(app.app) as c:
  r=c.post('/api/jobs',params={'resolution':'720','options':json.dumps({'zoom':'auto'})},headers={'x-file-ext':'mp4'},content=source.read_bytes());assert r.status_code==200
  j=r.json()['id'];d=wait(c,j);assert d['status']=='done' and len(d['applied_zoom'])>=1 and d['can_export'] and d['suggested_zoom'],d
  cues=d['captions'];cues[0]['text']='Texto corrigido depois do resultado.'
  assert c.post('/api/jobs/'+j+'/export',json={'captions':cues,'options':{'zoom':'manual'}}).status_code==422
  options={'zoom':'manual','zoom_moments':[{'start':.5,'end':2}],'speed':1.2}
  original_ff=app.ff;failed=[]
  def encoder_failure(args):
   if str(args[-1]).endswith('final.tmp.mp4') and not failed:failed.append(True);raise RuntimeError('injected encoder failure')
   return original_ff(args)
  app.ff=encoder_failure
  r=c.post('/api/jobs/'+j+'/export',json={'captions':cues,'options':options});assert r.status_code==200
  d=wait(c,j);assert d['status']=='error' and d['can_export'],d
  assert c.get('/api/jobs/'+j+'/video?preview=true').status_code==200
  r=c.post('/api/jobs/'+j+'/export',json={'captions':cues,'options':options});assert r.status_code==200,r.text
  d=wait(c,j);assert d['status']=='done' and d['options']['speed']==1.2 and len(d['applied_zoom'])==1,d
  assert d['captions'][0]['text']==cues[0]['text']
  assert c.get('/api/jobs/'+j+'/video?download=true').status_code==200
  app.ff(['-i',str(app.DATA/j/'final.mp4'),'-f','null','-'])
  print({'passed':True,'auto_without_keywords':True,'completed_job_reexport':True,'retry_after_failure':True,'speed':1.2})
 app.run=real
if __name__=='__main__':main()
