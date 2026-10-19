import os,tempfile,time,sys
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-cancel-')
import app
from fastapi.testclient import TestClient

def wait(c,j,status):
    for _ in range(100):
        d=c.get('/api/jobs/'+j).json()
        if d['status']==status:return d
        time.sleep(.03)
    raise AssertionError(d)

def slow(j,review):
    app.update(j,status='processing',message='test')
    app.run([sys.executable,'-c','import time; time.sleep(60)'])
    app.update(j,status='done',message='must not occur')

app.process=slow
with TestClient(app.app) as c:
    def create():
        r=c.post('/api/jobs',headers={'x-file-ext':'mp4'},content=b'0'*1024);assert r.status_code==200,r.text
        return r.json()['id']
    j=create();wait(c,j,'processing')
    for _ in range(100):
        if j in app.active_processes:break
        time.sleep(.01)
    p=app.active_processes[j]
    queued=create()
    assert c.post('/api/jobs/'+queued+'/cancel').status_code==200
    wait(c,queued,'cancelled')
    started=time.monotonic()
    assert c.post('/api/jobs/'+j+'/cancel').status_code==200
    wait(c,j,'cancelled')
    assert time.monotonic()-started<3
    assert p.poll() is not None
    assert not (app.DATA/j).exists()
    assert c.post('/api/jobs/'+j+'/cancel').status_code==200
    def finish(j,review):app.update(j,status='review',progress=75,message='new work accepted')
    app.process=finish
    next_job=create();wait(c,next_job,'review')
    assert c.delete('/api/jobs/'+j).status_code==200
    assert c.get('/api/jobs/'+j).status_code==404
    print('PASS: running child stopped; queued task cancelled; files removed; repeated cancel safe; next video processed.')
