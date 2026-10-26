import asyncio,hashlib,json,tempfile,threading,time,unittest,subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
import app as m

class PartialRequest:
 async def stream(self):
  yield b'partial'
  raise RuntimeError('client disconnected')

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.calls=[]
  self.old=m.DATA;m.DATA=self.root;m.jobs.clear();m.cancel_events.clear();m.job_futures.clear();m.upload_chunk_locks.clear()
  self.pool=patch.object(m,'pool',SimpleNamespace(submit=lambda *a:self.calls.append(a)));self.pool.start();self.client=TestClient(m.app);self.client.__enter__()
 def tearDown(self):
  self.client.__exit__(None,None,None);self.pool.stop();m.DATA=self.old;self.tmp.cleanup();m.jobs.clear();m.cancel_events.clear();m.job_futures.clear();m.upload_chunk_locks.clear()
 def create(self,size=4000):
  payload={'client_id':'a'*32,'name':'video.mp4','size':size,'fingerprint':'b'*64};r=self.client.post('/api/uploads',json=payload);self.assertEqual(r.status_code,200);return r.json()['id'],payload
 def test_resume_rollback_offsets_lost_ack_and_finish_once(self):
  j,payload=self.create();self.assertEqual(self.client.post('/api/uploads',json=payload).json()['id'],j);self.assertEqual(len(m.jobs),1)
  self.assertEqual(self.client.put('/api/uploads/'+j+'?offset=0',content=b'a'*2000).status_code,200)
  with self.assertRaises(RuntimeError):asyncio.run(m.upload_chunk(j,PartialRequest(),2000))
  self.assertEqual((self.root/j/'input').read_bytes(),b'a'*2000);self.assertEqual(m.jobs[j]['upload_received'],2000)
  self.assertEqual(self.client.put('/api/uploads/'+j+'?offset=0',content=b'a'*2000).status_code,409)
  self.assertEqual(self.client.post('/api/uploads/'+j+'/complete').status_code,409)
  self.assertEqual(self.client.put('/api/uploads/'+j+'?offset=2000',content=b'b'*2000).status_code,200)
  for _ in range(2):self.assertEqual(self.client.post('/api/uploads/'+j+'/complete').status_code,200)
  self.assertEqual(len(self.calls),1);self.assertEqual((self.root/j/'input').read_bytes(),b'a'*2000+b'b'*2000)
 def test_bounds_and_cancel(self):
  j,_=self.create();self.assertEqual(self.client.put('/api/uploads/'+j+'?offset=0',content=b'x'*4001).status_code,413);self.assertEqual((self.root/j/'input').stat().st_size,0)
  m.upload_chunk_locks[j].acquire()
  try:self.assertEqual(self.client.put('/api/uploads/'+j+'?offset=0',content=b'x'*1000).status_code,409)
  finally:m.upload_chunk_locks[j].release()
  self.assertEqual(self.client.post('/api/jobs/'+j+'/cancel').json()['status'],'cancelled');self.assertFalse((self.root/j).exists())
  self.assertEqual(self.client.post('/api/uploads',json={'client_id':'c'*32,'name':'video.mp4','size':2*1024**3+1,'fingerprint':'b'*64}).status_code,422)
 def test_real_video_processes_without_browser_polling(self):
  source=self.root/'synthetic.mp4';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x284:rate=30:duration=3','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-c:v','libx264','-preset','ultrafast','-c:a','aac','-y',str(source)],check=True)
  raw=source.read_bytes();j,payload=self.create(len(raw));cut=len(raw)//2
  self.assertEqual(self.client.put('/api/uploads/'+j+'?offset=0',content=raw[:cut]).status_code,200)
  with self.assertRaises(RuntimeError):asyncio.run(m.upload_chunk(j,PartialRequest(),cut))
  self.assertEqual(self.client.put('/api/uploads/'+j+'?offset='+str(cut),content=raw[cut:]).status_code,200)
  self.assertEqual(hashlib.sha256((self.root/j/'input').read_bytes()).digest(),hashlib.sha256(raw).digest())
  m.jobs[j]['options'].update(subtitles=False,zoom='off',remove_retakes=False,trim_edges=False);m.jobs[j].update(width=720,height=1280,resolution='720')
  # Restore the real queue; no status HTTP requests while the worker processes.
  self.pool.stop();self.assertEqual(self.client.post('/api/uploads/'+j+'/complete').status_code,200)
  deadline=time.monotonic()+60
  while m.jobs[j]['status'] not in ['done','error'] and time.monotonic()<deadline:time.sleep(.05)
  self.assertEqual(m.jobs[j]['status'],'done',m.jobs[j].get('message'))
  r=self.client.get('/api/jobs/'+j+'/video?download=true');self.assertEqual(r.status_code,200)
  final=self.root/'download.mp4';final.write_bytes(r.content);subprocess.run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'],check=True)
  self.pool.start()
if __name__=='__main__':unittest.main()
