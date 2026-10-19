"""Real face detection and 4K MP4 export; known transcript isolates editing."""
import os,tempfile,json,time,resource
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-face-')
import app
from fastapi.testclient import TestClient

def wait(c,j):
    for _ in range(500):
        d=c.get('/api/jobs/'+j).json()
        if d['status'] in ['review','done','error']:return d
        time.sleep(.2)
    raise AssertionError('timeout')

def main():
    import matplotlib
    portrait=Path(matplotlib.get_data_path())/'sample_data/grace_hopper.jpg'
    source=app.DATA/'portrait.mp4'
    # Off-center face verifies the anchor differs from a generic center zoom.
    app.ff(['-loop','1','-i',str(portrait),'-f','lavfi','-i','sine=frequency=440:duration=2.5:sample_rate=48000','-t','2.5','-vf','scale=400:-2,pad=720:1280:0:100:color=0x102421','-r','30','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac',str(source)])
    original=app.run
    def fixture(args,timeout=1800):
        if len(args)>1 and args[1].endswith('transcribe_task.py'):return json.dumps([{'start':.1,'end':2.1,'text':'Atenção ao prazo importante!'}]),''
        return original(args,timeout)
    app.run=fixture
    opts={'zoom':'manual','zoom_target':'face','zoom_moments':[{'start':.1,'end':2.2}]}
    with TestClient(app.app) as c:
        r=c.post('/api/jobs',params={'resolution':'2160','options':json.dumps(opts)},headers={'x-file-ext':'mp4'},content=source.read_bytes());assert r.status_code==200,r.text
        j=r.json()['id'];d=wait(c,j);assert d['status']=='done',d
        assert len(d['applied_zoom'])==1,d
        m=d['applied_zoom'][0];assert 0<m['face_x']<.45 and 0<m['face_y']<.45,m
        final=app.DATA/j/'final.mp4';meta=app.probe(final);video=next(s for s in meta['streams'] if s['codec_type']=='video');audio=next(s for s in meta['streams'] if s['codec_type']=='audio');assert (video['width'],video['height'],video['codec_name'],audio['codec_name'])==(2160,3840,'h264','aac')
        app.ff(['-i',str(final),'-f','null','-'])
        app.ff(['-ss','1.1','-i',str(final),'-frames:v','1','-vf','scale=360:640',str(app.DATA/'face-frame.png')])
        assert len(c.get('/api/jobs/'+j+'/video?download=true').content)>1000
        # No face: explicitly report omitted zoom rather than claiming success.
        blank=app.DATA/'blank.mp4';app.ff(['-f','lavfi','-i','color=c=green:s=180x320:r=30:d=2.5','-f','lavfi','-i','sine=frequency=440:duration=2.5','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-shortest',str(blank)])
        r=c.post('/api/jobs',params={'resolution':'720','options':json.dumps(opts)},headers={'x-file-ext':'mp4'},content=blank.read_bytes());assert r.status_code==200,r.text
        none=wait(c,r.json()['id']);assert none['status']=='done' and not none['applied_zoom'] and 'Rosto não detectado' in none['zoom_note'],none
        child=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024;server=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        assert child+server<450,(child,server)
        print(json.dumps({'passed':True,'dimensions':[video['width'],video['height']],'anchor':m,'no_face_fallback':'PASS','peak_child_mb':child,'python_mb':server,'frame':str(app.DATA/'face-frame.png')}),flush=True)
    app.run=original
if __name__=='__main__':main()
