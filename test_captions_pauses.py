"""Real cuts/no-caption export and adding/removing captions on reexport."""
import json,os,tempfile,time,wave
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-toggle-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
 for _ in range(240):
  d=c.get('/api/jobs/'+j).json()
  if d['status'] in ['done','review','error']:return d
  time.sleep(.1)
 raise AssertionError('timeout')

def main():
 source=app.DATA/'pauses.mp4'
 app.ff(['-f','lavfi','-i','color=c=green:s=180x320:r=30:d=6','-f','lavfi','-i','sine=frequency=440:duration=6:sample_rate=48000','-af',"volume=enable='between(t,1,1.4)+between(t,3,3.4)+between(t,4,5)':volume=0",'-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
 real=app.run;calls=[]
 def fixture(args,timeout=1800):
  if len(args)>1 and args[1].endswith('transcribe_task.py'):
   calls.append(args)
   return json.dumps([{'start':.2,'end':.7,'text':'Legenda adicionada.'}]),''
  return real(args,timeout)
 app.run=fixture
 with TestClient(app.app) as c:
  results=[]
  for mode in ['natural','dynamic']:
   opts={'subtitles':False,'zoom':'off','remove_retakes':False,'pause_mode':mode,'transcription_hint':'João Gualberto'}
   r=c.post('/api/jobs',params={'resolution':'720','review':'true','options':json.dumps(opts)},headers={'x-file-ext':'mp4'},content=source.read_bytes());assert r.status_code==200,r.text
   j=r.json()['id'];d=wait(c,j);assert d['status']=='done' and d['captions']==[] and not calls,d
   assert (app.DATA/j/'final.mp4').read_bytes()==(app.DATA/j/'edited.mp4').read_bytes()
   assert not (app.DATA/j/'captions.ass').exists()
   with wave.open(str(app.DATA/j/'voice.wav')) as w:
    assert w.getnchannels()==1 and w.getframerate()==16000
    assert abs(w.getnframes()/16000-d['edited_seconds'])<.15
   results.append(d['edited_seconds'])
  assert results[1]<results[0]-.25,results
  # Enable captions later: transcription is generated once using saved PCM/hint.
  r=c.post('/api/jobs/'+j+'/export',json={'options':{'subtitles':True,'zoom':'off','pause_mode':'natural'}});assert r.status_code==200,r.text
  d=wait(c,j);assert d['status']=='done' and len(calls)==1 and calls[0][-1]=='João Gualberto',d
  assert d['options']['pause_mode']=='dynamic'
  assert (app.DATA/j/'captions.ass').exists()
  assert (app.DATA/j/'final.mp4').read_bytes()!=(app.DATA/j/'edited.mp4').read_bytes()
  r=c.post('/api/jobs/'+j+'/export',json={'captions':d['captions'],'options':{'subtitles':False,'zoom':'off'}});assert r.status_code==200
  d=wait(c,j);assert d['status']=='done' and len(calls)==1
  assert (app.DATA/j/'final.mp4').read_bytes()==(app.DATA/j/'edited.mp4').read_bytes()
  app.ff(['-i',str(app.DATA/j/'final.mp4'),'-f','null','-'])
  print({'passed':True,'natural_seconds':results[0],'dynamic_seconds':results[1],'skip_transcription':True,'add_remove_on_reexport':True,'pcm_timeline_aligned':True})
 app.run=real
if __name__=='__main__':main()
