"""Real FFmpeg edge trim and explicit restart removal with word-aligned cues."""
import os,tempfile,time,json
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-edges-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
 for _ in range(300):
  d=c.get('/api/jobs/'+j).json()
  if d['status'] in ['done','review','error']:return d
  time.sleep(.1)
 raise AssertionError('timeout')

def main():
 # The old implementation retained a stray piece from the first/last silence.
 log='silence_start: 0\nsilence_end: 1\nsilence_start: 3\nsilence_end: 5'
 assert all(abs(a-b)<.001 for a,b in zip(app.intervals(log,5)[0],(.82,3.16)))
 assert app.intervals(log,5,trim_edges=False)==[(0,5)]
 source=app.DATA/'source.mp4'
 app.ff(['-f','lavfi','-i','testsrc2=s=180x320:r=30:d=8','-f','lavfi','-i','sine=frequency=440:duration=8:sample_rate=48000','-af',"volume=enable='between(t,0,1)+between(t,6,8)':volume=0",'-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
 # Transcript supplied on the clipped PCM timeline. Restart spans cues.
 words=[{'text':'Tentativa','start':.2,'end':.6},{'text':'inicial.','start':.7,'end':1.1},{'text':'Errei','start':1.4,'end':1.7},{'text':'aqui','start':1.8,'end':2.0},{'text':'vou','start':2.1,'end':2.3},{'text':'começar','start':2.4,'end':2.7},{'text':'de','start':2.8,'end':2.9},{'text':'novo.','start':3.0,'end':3.2},{'text':'Fala','start':3.5,'end':3.9},{'text':'correta','start':4.0,'end':4.4},{'text':'agora.','start':4.5,'end':4.9}]
 def cue(ws):return {'start':ws[0]['start'],'end':ws[-1]['end'],'text':' '.join(w['text'] for w in ws),'words':ws}
 cues=[cue(words[:5]),cue(words[5:8]),cue(words[8:])]
 assert 3.3<app.restart_cut(cues,5.4)<3.5
 # Mentioning errors as the topic must not trigger a cut.
 assert app.restart_cut([cue([{'text':'O erro no contrato exige revisão.','start':0,'end':1}])],5) is None
 assert app.restart_cut([cue([{'text':'Errei na análise do contrato.','start':0,'end':1}])],5) is None
 real=app.run
 def fixture(args,timeout=1800):
  if len(args)>1 and args[1].endswith('transcribe_task.py'):return json.dumps(cues),''
  return real(args,timeout)
 app.run=fixture
 with TestClient(app.app) as c:
  opts={'zoom':'off','remove_retakes':True,'trim_edges':True}
  r=c.post('/api/jobs',params={'resolution':'720','review':'true','options':json.dumps(opts)},headers={'x-file-ext':'mp4'},content=source.read_bytes());assert r.status_code==200,r.text
  j=r.json()['id'];d=wait(c,j);assert d['status']=='review',d
  assert 3.3<d['retake_removed_seconds']<3.5 and 1.7<d['edited_seconds']<2.3,d
  assert 'Tentativa' not in str(d['captions']) and 'Errei' not in str(d['captions']) and 'Fala correta agora.' in str(d['captions'])
  assert d['captions'][0]['start']<.25
  assert c.post('/api/jobs/'+j+'/export',json={'captions':d['captions'],'options':opts}).status_code==200
  d=wait(c,j);assert d['status']=='done',d
  app.ff(['-i',str(app.DATA/j/'final.mp4'),'-f','null','-'])
  assert c.get('/api/jobs/'+j+'/video?download=true').status_code==200
  print({'passed':True,'leading_trailing_trim':True,'restart_removed_seconds':d['retake_removed_seconds'],'output_seconds':d['output_seconds'],'captions':d['captions']})
 app.run=real
if __name__=='__main__':main()
