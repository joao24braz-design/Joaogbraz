"""Critical integration test: real FFmpeg, synthetic speech-band audio, injected captions.
This does not claim to validate Whisper accuracy or model availability.
"""
import json, os, tempfile, time
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-test-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
    for _ in range(180):
        d=c.get('/api/jobs/'+j).json()
        if d['status'] in ['review','done','error']: return d
        time.sleep(.5)
    raise AssertionError('timeout')

def main(resolution='1080'):
    sample=Path(os.environ['JG_DATA'])/'sample.mp4'
    app.ff(['-f','lavfi','-i','color=c=0x254437:s=180x320:r=15:d=6','-f','lavfi','-i',"sine=frequency=440:duration=6:sample_rate=48000",'-af',"volume=enable='between(t,2,4)':volume=0",'-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(sample)])
    original_run=app.run
    def fixture_run(args,timeout=1800):
        if len(args)>1 and args[1].endswith('transcribe_task.py'):
            return json.dumps([{'start':.2,'end':1.3,'text':'Teste de legenda profissional.'},{'start':2.4,'end':3.3,'text':'Segunda frase com cobre.'}]),''
        return original_run(args,timeout)
    app.run=fixture_run
    with TestClient(app.app) as c:
        assert c.get('/').status_code==200
        assert c.post('/api/jobs',headers={'x-file-ext':'exe'},content=b'x'*1000).status_code==415
        assert c.post('/api/jobs',headers={'x-file-ext':'mp4','Origin':'https://other.example'},content=b'x'*1000).status_code==403
        r=c.post('/api/jobs?review=true&resolution='+resolution,headers={'x-file-ext':'mp4'},content=sample.read_bytes()); assert r.status_code==200,r.text
        j=r.json()['id']; d=wait(c,j); assert d['status']=='review',d
        assert d['edited_seconds']<5 and d['edited_seconds']>3.5,d
        assert c.get('/api/jobs/'+j+'/video?preview=true').status_code==200
        assert c.post('/api/jobs/'+j+'/export',json={'captions':[{'start':0,'end':100,'text':'invalid'}]}).status_code==422
        d['captions'][0]['text']='Texto corrigido antes da exportação.'
        assert c.post('/api/jobs/'+j+'/export',json={'captions':d['captions']}).status_code==200
        d=wait(c,j); assert d['status']=='done',d
        r=c.get('/api/jobs/'+j+'/video?download=true'); assert r.status_code==200 and len(r.content)>1000
        assert 'attachment' in r.headers['content-disposition']
        info=app.probe(app.DATA/j/'final.mp4'); v=next(s for s in info['streams'] if s['codec_type']=='video'); a=next(s for s in info['streams'] if s['codec_type']=='audio')
        assert (v['width'],v['height'],v['codec_name'],a['codec_name'])==((720 if resolution=='720' else 1080),(1280 if resolution=='720' else 1920),'h264','aac')
        app.ff(['-i',str(app.DATA/j/'final.mp4'),'-f','null','-'])
        app.ff(['-ss','0.6','-i',str(app.DATA/j/'final.mp4'),'-frames:v','1',str(Path(os.environ['JG_DATA'])/'frame.png')])
        print({'passed':True,'before':d['original_seconds'],'after':d['edited_seconds'],'video':v['codec_name'],'audio':a['codec_name'],'frame':str(Path(os.environ['JG_DATA'])/'frame.png'),'transcription':'injected fixture, not tested'})
        assert c.delete('/api/jobs/'+j).status_code==200
        assert c.get('/api/jobs/'+j).status_code==404
    app.run=original_run
if __name__=='__main__': main()
