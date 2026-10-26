"""Exercise the real streaming handler with a counting sink, without allocating/writing 2 GB."""
import ast,asyncio,json,secrets,threading,time,typing,unittest
from pathlib import Path
from types import SimpleNamespace

class HTTPException(Exception):
 def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
class Sink:
 def __init__(self):self.written=0
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def write(self,chunk):self.written+=len(chunk)
class Target:
 def __init__(self):self.sink=Sink();self.created=False
 def __truediv__(self,name):return self
 def mkdir(self,**kwargs):self.created=True
 def open(self,*args):return self.sink
class Request:
 def __init__(self,size,declared=None,disconnect=False):
  self.size=size;self.read=False;self.disconnect=disconnect;self.headers={'x-file-ext':'mp4'}
  if declared is not None:self.headers['content-length']=str(declared)
 async def stream(self):
  self.read=True;block=b'x'*(1024*1024);left=self.size
  while left:
   n=min(left,len(block));yield block if n==len(block) else block[:n];left-=n
  if self.disconnect:raise RuntimeError('disconnected')
class UploadLimit(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  tree=ast.parse(Path('app.py').read_text());handler=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='upload');handler.decorator_list=[]
  constant=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAX_BYTES' for t in n.targets))
  self.target=Target();self.submissions=[];self.cleaned=[]
  self.ns={'Literal':typing.Literal,'Request':Request,'HTTPException':HTTPException,'secrets':secrets,'threading':threading,'time':time,'guard':threading.RLock(),'jobs':{},'cancel_events':{},'job_futures':{},'DATA':self.target,'EditOptions':SimpleNamespace(model_validate_json=lambda _:SimpleNamespace(model_dump=lambda:{})),'output_size':lambda *a:(1080,1920),'shutil':SimpleNamespace(rmtree=lambda *a,**k:self.cleaned.append(True)),'pool':SimpleNamespace(submit=lambda *a:self.submissions.append(a)),'execute_job':object(),'process':object()}
  self.ns['update']=lambda j,**kw:self.ns['jobs'][j].update(kw)
  exec(compile(ast.fix_missing_locations(ast.Module(body=[constant,handler],type_ignores=[])),'app.py','exec'),self.ns)
 async def test_above_old_limit_and_exact_2gb_accepted(self):
  for size in [301*1024*1024,2*1024**3]:
   self.setUp();r=Request(size,declared=size);result=await self.ns['upload'](r)
   self.assertIn('id',result);self.assertEqual(self.target.sink.written,size);self.assertEqual(len(self.submissions),1)
 async def test_oversized_header_rejected_before_reading(self):
  r=Request(0,declared=2*1024**3+1)
  with self.assertRaises(HTTPException) as e:await self.ns['upload'](r)
  self.assertEqual(e.exception.status_code,413);self.assertFalse(r.read);self.assertFalse(self.target.created);self.assertFalse(self.ns['jobs'])
 async def test_stream_enforces_limit_without_header_and_cleans(self):
  with self.assertRaises(HTTPException) as e:await self.ns['upload'](Request(2*1024**3+1))
  self.assertEqual(e.exception.status_code,413);self.assertEqual(self.target.sink.written,2*1024**3);self.assertFalse(self.ns['jobs']);self.assertTrue(self.cleaned);self.assertFalse(self.submissions)
 async def test_disconnect_cleans_partial_file(self):
  with self.assertRaises(RuntimeError):await self.ns['upload'](Request(2048,disconnect=True))
  self.assertFalse(self.ns['jobs']);self.assertTrue(self.cleaned)
if __name__=='__main__':unittest.main()
