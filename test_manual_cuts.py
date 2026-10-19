"""Real manual cuts, non-cumulative reexport, caption/zoom clock and intensity."""
import os,tempfile,time,json,re,wave,struct
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-manual-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
 for _ in range(250):
  d=c.get('/api/jobs/'+j).json()
  if d['status'] in ['done','review','error']:return d
  time.sleep(.1)
 raise AssertionError('timeout')

def main():
 source=app.DATA/'source.mp4'
 app.ff(['-f','lavfi','-i','testsrc2=s=180x320:r=30:d=8','-f','lavfi','-i','aevalsrc=0.3*sin(2*PI*(220+110*floor(t))*t):s=48000:d=8','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
 words=[{'start':i+.1,'end':i+.8,'text':str(i)} for i in range(8)]
 cues=[{'start':w['start'],'end':w['end'],'text':w['text'],'words':[w]} for w in words]
 real=app.run
 def fixture(args,timeout=1800):
  if len(args)>1 and args[1].endswith('transcribe_task.py'):return json.dumps(cues),''
  return real(args,timeout)
 app.run=fixture
 with TestClient(app.app) as c:
  r=c.post('/api/jobs',params={'resolution':'720','review':'true','options':json.dumps({'zoom':'off'})},headers={'x-file-ext':'mp4'},content=source.read_bytes());assert r.status_code==200
  j=r.json()['id'];d=wait(c,j);assert d['status']=='review',d
  baseline=(app.DATA/j/'edited.mp4').read_bytes();base_duration=d['edited_seconds']
  def export(opts,caption_list=None):
   r=c.post('/api/jobs/'+j+'/export',json={'captions':d['captions'] if caption_list is None else caption_list,'options':opts});assert r.status_code==200,r.text
   out=wait(c,j);assert out['status']=='done',out
   app.ff(['-i',str(app.DATA/j/'final.mp4'),'-f','null','-'])
   assert (app.DATA/j/'edited.mp4').read_bytes()==baseline
   assert out['edited_seconds']==base_duration
   return out
  opts={'zoom':'manual','zoom_percent':50,'zoom_moments':[{'start':1,'end':3},{'start':5,'end':6.8}],'trim_start':1,'trim_end':7,'remove_ranges':[{'start':3,'end':5}],'speed':1.2}
  d=export(opts);assert abs(d['output_seconds']-4/1.2)<.12,d
  assert d['applied_zoom_percent']==50 and abs(d['selected_seconds']-4)<.01
  assert [(round(m['start'],2),round(m['end'],2)) for m in d['applied_zoom']]==[(0,2),(2,3.8)]
  ass=(app.DATA/j/'captions.ass').read_text();assert ',,3\n' not in ass and ',,4\n' not in ass
  texts=[line.rsplit(',,',1)[-1] for line in ass.splitlines() if line.startswith('Dialogue:')];assert len(texts)==4,texts
  # Audio landmarks verify which source sections survived the middle cut.
  for position,expected in [(.5,330),(2.1,770)]:
   audio=app.DATA/'landmark.wav'
   app.ff(['-ss',str(position),'-i',str(app.DATA/j/'final.mp4'),'-t','0.2','-vn','-ac','1','-ar','16000',str(audio)])
   with wave.open(str(audio)) as w:samples=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
   crossings=sum((a<0)!=(b<0) for a,b in zip(samples,samples[1:]));frequency=crossings/(2*(len(samples)/16000));assert abs(frequency-expected)<20,(position,frequency,expected)
  # Another export uses the same base, so cuts do not accumulate.
  d=export({**opts,'zoom_percent':100});assert abs(d['output_seconds']-4/1.2)<.12
  d=export({'zoom':'off','subtitles':False});assert abs(d['output_seconds']-base_duration)<.05
  assert (app.DATA/j/'final.mp4').read_bytes()==baseline
  for invalid in [{'zoom_percent':101},{'trim_start':9},{'trim_start':7,'trim_end':2},{'remove_ranges':[{'start':0,'end':8}]},{'remove_ranges':[{'start':4,'end':9}]}]:
   r=c.post('/api/jobs/'+j+'/export',json={'captions':d['captions'],'options':{'zoom':'off',**invalid}});assert r.status_code==422,(invalid,r.text)
  # Overlap is removed once, boundaries are frame-aligned.
  keep=app.manual_keep(8,app.EditOptions(remove_ranges=[{'start':2,'end':4},{'start':3,'end':5}]))
  assert keep==[(0,2),(5,8)],keep
  split=[{'start':1,'end':3,'text':'um dois tres quatro','words':[{'start':1,'end':1.5,'text':'um'},{'start':1.5,'end':2,'text':'dois'},{'start':2,'end':2.5,'text':'tres'},{'start':2.5,'end':3,'text':'quatro'}]}]
  mapped,estimated=app.map_captions(split,[(0,1.5),(2.5,4)]);assert [x['text'] for x in mapped]==['um','quatro'] and not estimated,mapped
  assert '0.5*sin' in app.zoom_filter([{'start':0,'end':2}],720,1280,50)
  assert '1.0*sin' in app.zoom_filter([{'start':0,'end':2,'face_x':.3,'face_y':.3}],720,1280,100)
  assert not list((app.DATA/j).glob('manual*'))
  assert len(c.get('/api/jobs/'+j+'/video?download=true').content)>1000
  print({'passed':True,'base_seconds':base_duration,'cut_seconds':4,'speed':1.2,'zoom_percent':[50,100],'left_right_middle':True,'restore_original_edit':True,'word_caption_mapping':True,'invalid_parameters_rejected':True})
 app.run=real
if __name__=='__main__':main()
