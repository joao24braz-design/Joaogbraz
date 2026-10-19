"""Regression: several cuts from 4K input with bounded FFmpeg RSS."""
import os,json,re,resource,tempfile,threading,time
from pathlib import Path
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-memory-')
import app
j='a'*48;d=app.DATA/j;d.mkdir();app.jobs[j]={'created':time.time(),'status':'processing'};app.cancel_events[j]=threading.Event()
source=d/'input.mp4'
app.ff(['-f','lavfi','-i','color=c=0x24483c:s=2160x3840:r=30:d=11','-f','lavfi','-i','sine=frequency=440:duration=11:sample_rate=48000','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
original_run=app.run;peaks=[]
def measured(args,timeout=1800):
    if args[0]=='ffmpeg':
        out,err=original_run(args,timeout)
        peaks.append(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss);return out,err
    return original_run(args,timeout)
app.run=measured
app.cut_video(j,source,d,[(0,1.5),(3,4.5),(6,7.5),(9,10.5)])
app.render(j,[{'start':0,'end':1.4,'text':'Teste de vídeo 4K com cortes.'}])
assert app.jobs[j]['status']=='done',app.jobs[j]
info=app.probe(d/'final.mp4');duration=float(info['format']['duration']);assert 5.9<duration<6.3,duration
app.ff(['-i',str(d/'final.mp4'),'-f','null','-'])
server_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
assert max(peaks)+server_kb<450*1024,(peaks,server_kb)
print(json.dumps({'passed':True,'input':'2160x3840','clips':4,'output_seconds':duration,'peak_ffmpeg_mb':round(max(peaks)/1024,1),'python_peak_mb':round(server_kb/1024,1),'file':str(d/'final.mp4')}))
