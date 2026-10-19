"""Real FFmpeg integration: formats, acceleration, subtitle styling and zoom.
Whisper is replaced with a known transcript to isolate editing and timing.
"""
import json, os, tempfile, time
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-options-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
    for _ in range(240):
        data=c.get('/api/jobs/'+j).json()
        if data['status'] in ['review','done','error']: return data
        time.sleep(.25)
    raise AssertionError('timeout')

def main():
    source=app.DATA/'sample.mp4'
    app.ff(['-f','lavfi','-i','testsrc2=s=180x320:r=30:d=6','-f','lavfi','-i','sine=frequency=440:duration=6:sample_rate=48000','-af',"volume=enable='between(t,2,4)':volume=0",'-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
    real=app.run
    def fixture(args,timeout=1800):
        if len(args)>1 and args[1].endswith('transcribe_task.py'):
            return json.dumps([{'start':.3,'end':1.6,'text':'Atenção ao prazo importante!'},{'start':2.5,'end':3.5,'text':'Seus direitos precisam de cuidado.'}]),''
        return real(args,timeout)
    app.run=fixture
    with TestClient(app.app) as c:
        assert c.post('/api/jobs?options='+json.dumps({'speed':2.1}),headers={'x-file-ext':'mp4'},content=source.read_bytes()).status_code==422
        assert c.post('/api/jobs?format=invalid',headers={'x-file-ext':'mp4'},content=source.read_bytes()).status_code==422
        for format,framing,style,speed,zoom in [('reels','contain','premium',1,'off'),('story','cover','clean',1.1,'auto'),('feed','cover','box',2,'manual'),('square','contain','premium',1.5,'auto')]:
            r=c.post('/api/jobs',params={'review':'true','resolution':'720','format':format,'framing':framing},headers={'x-file-ext':'mp4'},content=source.read_bytes());assert r.status_code==200,r.text
            j=r.json()['id'];d=wait(c,j);assert d['status']=='review',d
            opts={'speed':speed,'subtitle_size':'large','subtitle_style':style,'text_color':'#FFFFFF','accent_color':'#BC7733','zoom':zoom,'zoom_moments':[{'start':.2,'end':1.8}] if zoom=='manual' else []}
            body={'captions':d['captions'],'options':opts}
            invalid={**body,'options':{**opts,'zoom':'manual','zoom_moments':[{'start':1,'end':99}]}}
            assert c.post('/api/jobs/'+j+'/export',json=invalid).status_code==422
            assert c.post('/api/jobs/'+j+'/export',json={**body,'options':{**opts,'text_color':'inject'}}).status_code==422
            assert c.post('/api/jobs/'+j+'/export',json=body).status_code==200
            d=wait(c,j);assert d['status']=='done',d
            assert abs(d['output_seconds']-d['edited_seconds']/speed)<.2,d
            meta=app.probe(app.DATA/j/'final.mp4');v=next(s for s in meta['streams'] if s['codec_type']=='video');a=next(s for s in meta['streams'] if s['codec_type']=='audio')
            assert (v['width'],v['height'])==app.output_size('720',format)
            assert (v['codec_name'],a['codec_name'])==('h264','aac')
            assert len(d['applied_zoom'])==(0 if zoom=='off' else 1),d
            text=(app.DATA/j/'captions.ass').read_text();assert app.stamp(.3/speed) in text and 'BC7733' not in text
            assert 'Style: Premium,DejaVu Sans,72' in text
            app.ff(['-i',str(app.DATA/j/'final.mp4'),'-f','null','-'])
            if speed==2:
                import wave,numpy as np
                audio=app.DATA/'tone.wav';app.ff(['-i',str(app.DATA/j/'final.mp4'),'-t','0.4','-vn','-ar','16000','-ac','1',str(audio)])
                with wave.open(str(audio)) as w: samples=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16)
                freq=np.fft.rfftfreq(len(samples),1/16000)[np.abs(np.fft.rfft(samples)).argmax()];assert abs(freq-440)<15,freq
            assert len(c.get('/api/jobs/'+j+'/video?download=true').content)>1000
            assert c.delete('/api/jobs/'+j).status_code==200
            print({'format':format,'speed':speed,'style':style,'zoom':zoom,'duration':d['output_seconds'],'dimensions':[v['width'],v['height']],'pass':True},flush=True)
    app.run=real
if __name__=='__main__':main()
