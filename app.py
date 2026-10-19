"""JG Reels AI: single-user local service. No paid APIs."""
import signal, sys, asyncio, base64, contextlib, json, logging, math, os, re, secrets, shutil, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).parent
DATA=Path(os.getenv('JG_DATA',str(ROOT/'data'))).resolve(); DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
MAX_BYTES=300*1024*1024; TTL=24*3600
jobs={}; guard=threading.RLock(); pool=ThreadPoolExecutor(max_workers=1)
model=None

class ZoomMoment(BaseModel):
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)

class EditOptions(BaseModel):
    speed:float=Field(default=1,ge=1,le=2,allow_inf_nan=False,multiple_of=0.1)
    subtitle_size:Literal['small','medium','large']='medium'
    subtitle_style:Literal['premium','clean','box']='premium'
    text_color:str=Field(default='#F7F5F4',pattern=r'^#[0-9a-fA-F]{6}$')
    accent_color:str=Field(default='#C49C7B',pattern=r'^#[0-9a-fA-F]{6}$')
    zoom:Literal['off','auto','manual']='off'
    zoom_target:Literal['center','face']='center'
    transcription_hint:str=Field(default='',max_length=300)
    subtitles:bool=True
    pause_mode:Literal['natural','dynamic']='natural'
    trim_edges:bool=True
    remove_retakes:bool=True
    zoom_moments:list[ZoomMoment]=Field(default_factory=list,max_length=8)

def output_size(resolution,format):
    width=int(resolution)
    return width,{'reels':width*16//9,'story':width*16//9,'feed':width*5//4,'square':width}[format]

def zoom_moments(cues,duration,options):
    if options.zoom=='off': return []
    if options.zoom=='manual':
        if not options.zoom_moments:raise ValueError('Informe ao menos um intervalo de zoom ou escolha Automático.')
        previous=0
        for moment in options.zoom_moments:
            if moment.end<=moment.start or moment.start<previous or moment.end>duration:
                raise ValueError('Use momentos de zoom em ordem, sem sobreposição, dentro do vídeo cortado.')
            previous=moment.end
        return [m.model_dump() for m in options.zoom_moments]
    # Editorial cues plus spaced fallback: no claim of full semantic understanding.
    def score(c):
        text=c['text']
        return (4*bool(re.search(r'\b(atenção|cuidado|importante|direito|direitos|prazo|dívida|dívidas|risco|nunca|precisa|segredo|principal)\b',text,re.I))
            +3*bool(re.search(r'\d|\b(mil|milhão|milhões|dinheiro|valor|patrimônio|colheitadeira)\b',text,re.I))
            +2*bool(re.search(r'\b(mas|porém|então|enquanto|só que)\b',text,re.I))
            +2*bool(re.search('[!?]',text)))
    chosen=[]
    def add(c):
        start=max(.2,c['start']-.15);end=min(duration-.15,max(c['end']+.2,start+1.2),start+3.5)
        if end-start<.6 or any(start<m['end']+4 and end>m['start']-4 for m in chosen):return False
        chosen.append({'start':round(start,3),'end':round(end,3)});return True
    for c in sorted(cues,key=score,reverse=True):
        if score(c):add(c)
        if len(chosen)>=4:break
    target=min(4,max(1,int(duration/15)+1))
    if cues and len(chosen)<target:
        for fraction in [.3,.6,.82,.15]:
            if len(chosen)>=target:break
            for c in sorted(cues,key=lambda c:abs((c['start']+c['end'])/2-duration*fraction)):
                if add(c):break
    return sorted(chosen,key=lambda m:m['start'])

def zoom_filter(moments,width,height):
    terms=[];xs=[];ys=[]
    for m in moments:
        start=m['start']*30;end=m['end']*30;length=end-start
        amount=.18 if 'face_x' in m else .10
        terms.append(f"if(between(on,{start:.3f},{end:.3f}),{amount}*sin(PI*(on-{start:.3f})/{length:.3f}),0)")
        if 'face_x' in m:
            xs.append(f"if(between(on,{start:.3f},{end:.3f}),{m['face_x']:.6f}-.5,0)")
            ys.append(f"if(between(on,{start:.3f},{end:.3f}),{m['face_y']:.6f}-.5,0)")
    cx='0.5' + ('+' + '+'.join(xs) if xs else '')
    cy='0.5' + ('+' + '+'.join(ys) if ys else '')
    return "zoompan=z='1+"+'+'.join(terms)+f"':x='max(0,min(iw-iw/zoom,iw*({cx})-iw/zoom/2))':y='max(0,min(ih-ih/zoom,ih*({cy})-ih/zoom/2))':d=1:s={width}x{height}:fps=30"

cancel_events={}; active_processes={}; job_futures={}; worker_context=threading.local()

class JobCancelled(Exception): pass

def stop_process(p):
    def send(sig):
        if p.poll() is None:
            with contextlib.suppress(ProcessLookupError): os.killpg(p.pid,sig)
    send(signal.SIGTERM)
    timer=threading.Timer(2,lambda:send(signal.SIGKILL)); timer.daemon=True; timer.start()

def finish_cancel(j):
    with guard:
        if j not in jobs: return
        shutil.rmtree(DATA/j,ignore_errors=True)
        jobs[j].update(status='cancelled',progress=0,message='Processamento cancelado. Você pode enviar outro vídeo.')

def execute_job(j,fn,*args):
    worker_context.job=j
    try:
        if cancel_events[j].is_set(): raise JobCancelled()
        fn(j,*args)
    except JobCancelled: pass
    finally:
        if cancel_events.get(j) and cancel_events[j].is_set(): finish_cancel(j)
        with guard:
            job_futures.pop(j,None); active_processes.pop(j,None)
        worker_context.job=None

def run(args, timeout=1800):
    j=getattr(worker_context,'job',None)
    event=cancel_events.get(j)
    with guard:
        if event and event.is_set(): raise JobCancelled()
        p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        if j: active_processes[j]=p
    try:
        try: out,err=p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL); p.communicate(); raise RuntimeError('Tempo limite de processamento atingido.')
        if event and event.is_set(): raise JobCancelled()
        if p.returncode:
            logging.error('Media/subprocess failed: %s',err[-1500:])
            raise RuntimeError('Falha no processamento de mídia. Verifique se o arquivo está íntegro.')
        return out,err
    finally:
        if j:
            with guard:
                if active_processes.get(j) is p: active_processes.pop(j,None)

def ff(args): return run(['ffmpeg','-nostdin','-hide_banner','-y','-threads','1','-filter_threads','1',*args])
def probe(p): return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],60)[0])
def update(j,**kw):
    with guard:
        if cancel_events.get(j) and cancel_events[j].is_set(): raise JobCancelled()
        jobs[j].update(kw)
def get(j):
    with guard:
        if j not in jobs: raise HTTPException(404,'Projeto expirado ou inexistente.')
        return dict(jobs[j])

def pause_settings(mode):
    return (.3,.08,.10) if mode=='dynamic' else (.6,.14,.18)

def intervals(log,duration,mode='natural',trim_edges=True):
    threshold,pad_after,pad_before=pause_settings(mode)
    gaps=[]; start=None
    for kind,value in re.findall(r'silence_(start|end):\s*([\d.]+)',log):
        if kind=='start': start=float(value)
        elif start is not None: gaps.append((start,min(duration,float(value)))); start=None
    if start is not None: gaps.append((start,duration))
    keep=[];pos=0
    for a,b in gaps:
        leading=a<=.03;trailing=b>=duration-.03
        if leading or trailing:
            if not trim_edges:continue
            if leading and trailing:raise ValueError('Não foi detectada fala suficiente. Confira o áudio do vídeo.')
            if leading:
                pos=max(pos,b-.18);continue
            left=min(duration,a+.16)
            if left>pos+.04:keep.append((pos,left))
            pos=duration;continue
        if b-a<threshold:continue
        left=min(duration,a+pad_after);right=max(left,b-pad_before)
        if left>pos+.04:keep.append((pos,left))
        pos=max(pos,right)
    if duration-pos>.04:keep.append((pos,duration))
    if sum(b-a for a,b in keep)<.35:raise ValueError('Não foi detectada fala suficiente. Confira o áudio do vídeo.')
    if len(keep)>200:raise ValueError('Muitas pausas detectadas. Use um vídeo mais curto ou com menos ruído.')
    return keep

def stamp(t):
    cs=round(max(0,t)*100); return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def ass_color(color):
    return '&H00'+color[5:7]+color[3:5]+color[1:3]

def ass_file(path,cues,options=None,format='reels'):
    options=options or EditOptions()
    canvas_height={'reels':1920,'story':1920,'feed':1350,'square':1080}[format]
    margin={'reels':370,'story':320,'feed':150,'square':120}[format]
    size={'small':44,'medium':58,'large':72}[options.subtitle_size]
    primary=ass_color(options.text_color);accent=ass_color(options.accent_color)
    border=3 if options.subtitle_style=='box' else 1
    outline=14 if border==3 else 3
    header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: {canvas_height}\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Premium,DejaVu Sans,{size},{primary},{accent},&H00110F0B,&H90000000,-1,0,0,0,100,100,0,0,{border},{outline},1,2,90,170,{margin},1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    lines=[]
    for c in cues:
        words=c['text'].replace('\\','').replace('{','').replace('}','').split()
        if not words: continue
        if options.subtitle_style=='premium':
            words[-1]='{\\c'+accent+'&}'+words[-1]+'{\\c'+primary+'&}'
        text=' '.join(words)
        lines.append(f"Dialogue: 0,{stamp(c['start']/options.speed)},{stamp(c['end']/options.speed)},Premium,,0,0,0,,{{\\fad(70,70)}}{text}")
    path.write_text(header+'\n'.join(lines),encoding='utf-8')

def transcribe(audio,hint=""):
    global model
    from faster_whisper import WhisperModel
    if model is None:
        model=WhisperModel(os.getenv('WHISPER_MODEL','base'),device='cpu',compute_type='int8',cpu_threads=1,num_workers=1,download_root=os.getenv('WHISPER_CACHE',str(ROOT/'models')))
    import wave
    import numpy as np
    with wave.open(str(audio),'rb') as source:
        samples=np.frombuffer(source.readframes(source.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
    # Standard 30-second context and bounded fallback avoid brittle short windows
    # and repetitive decoding on difficult speech. Hints are optional, not replacements.
    segments,_=model.transcribe(samples,language='pt',task='transcribe',beam_size=5,best_of=5,temperature=(0.0,0.2,0.4),word_timestamps=True,condition_on_previous_text=False,initial_prompt=hint.strip() or None)
    cues=[]
    for s in segments:
        words=[w for w in (s.words or []) if w.word.strip()]
        batch=[]
        for w in words:
            if batch and (len(batch)>=6 or w.end-batch[0].start>2.8 or len(' '.join(x.word for x in batch))+len(w.word)>44):
                cues.append({'start':batch[0].start,'end':batch[-1].end,'text':' '.join(x.word.strip() for x in batch),'words':[{'start':x.start,'end':x.end,'text':x.word.strip()} for x in batch]}); batch=[]
            batch.append(w)
        if batch: cues.append({'start':batch[0].start,'end':batch[-1].end,'text':' '.join(x.word.strip() for x in batch),'words':[{'start':x.start,'end':x.end,'text':x.word.strip()} for x in batch]})
    # Keep revision/export on a monotonic clock bounded by the actual PCM.
    duration=len(samples)/16000
    previous=0
    normalized=[]
    for cue in cues:
        start=min(duration,max(previous,cue['start']))
        end=min(duration,max(start,cue['end']))
        if end>start:
            normalized.append({**cue,'start':start,'end':end});previous=end
    cues=normalized
    if not cues: raise ValueError('A transcrição não reconheceu fala. Confira o áudio e tente novamente.')
    return cues

def render(j,cues):
    d=DATA/j
    try:
        update(j,status='exporting',progress=85,message='Incorporando legendas e exportando MP4…')
        job=get(j);options=EditOptions(**job.get('options',{}))
        moments=zoom_moments(cues,job['edited_seconds'],options)
        update(j,planned_zoom=moments)
        requested_moments=len(moments)
        if options.zoom_target=='face' and moments:
            update(j,message='Localizando o rosto nos momentos de zoom…')
            moments=json.loads(run([sys.executable,str(ROOT/'face_task.py'),str(d/'edited.mp4'),json.dumps(moments)],300)[0])
            update(j,message='Incorporando legendas e exportando MP4…')
        zoom_note=''
        if options.zoom_target=='face' and requested_moments>len(moments):
            zoom_note=f'Rosto não detectado em {requested_moments-len(moments)} trecho(s); esses trechos ficaram sem zoom.'
        elif options.zoom!='off' and not requested_moments:
            zoom_note='Nenhum momento de zoom selecionado. Use momentos manuais para indicar onde aproximar.'
        if options.subtitles: ass_file(d/'captions.ass',cues,options,job.get('format','reels'))
        filters=[]
        if moments: filters.append(zoom_filter(moments,job['width'],job['height']))
        if options.speed!=1: filters.append(f'setpts=(PTS-STARTPTS)/{options.speed}')
        if options.subtitles: filters.append(f"ass=filename='{d/'captions.ass'}'")
        audio=['-c:a','copy'] if options.speed==1 else ['-af',f'atempo={options.speed}','-c:a','aac','-b:a','160k']
        if filters:
            ff(['-i',str(d/'edited.mp4'),'-vf',','.join(filters),'-c:v','libx264','-threads','1','-preset','veryfast','-tune','zerolatency','-crf','21','-pix_fmt','yuv420p',*audio,'-movflags','+faststart',str(d/'final.tmp.mp4')])
        else:
            shutil.copyfile(d/'edited.mp4',d/'final.tmp.mp4')
        os.replace(d/'final.tmp.mp4',d/'final.mp4')
        update(j,status='done',progress=100,message='Seu vídeo está pronto.',captions=cues,output_seconds=float(probe(d/'final.mp4')['format']['duration']),applied_zoom=moments,zoom_note=zoom_note)
    except Exception as e: fail(j,e)

def fail(j,e):
    if isinstance(e,JobCancelled) or (cancel_events.get(j) and cancel_events[j].is_set()): return
    logging.exception('Job %s failed',j)
    msg=str(e) if isinstance(e,ValueError) else 'Processamento interrompido. Verifique FFmpeg, memória e acesso ao modelo Whisper. Consulte o registro do servidor.'
    update(j,status='error',message=msg,progress=0)

def cut_video(j,source,d,keep):
    # Bound decoder/encoder queues: never keep all trimmed source branches in RAM.
    width=jobs[j].get('width',1080);height=jobs[j].get('height',1920)
    fit=jobs[j].get('framing','contain')
    geometry=(f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}' if fit=='cover' else f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x091715')
    parts=[]
    for i,(a,b) in enumerate(keep):
        update(j,progress=25+int(25*i/len(keep)),message=f'Cortando trecho {i+1} de {len(keep)}…')
        part=d/f'part-{i:03d}.mkv'
        ff(['-ss',str(a),'-i',str(source),'-t',str(b-a),'-map','0:v:0','-map','0:a:0',
            '-vf',geometry+',setsar=1,fps=30',
            '-af','aresample=48000','-ac','2','-c:v','libx264','-threads','1','-preset','ultrafast','-tune','zerolatency',
            '-crf','18','-pix_fmt','yuv420p','-c:a','pcm_s16le','-avoid_negative_ts','make_zero',str(part)])
        parts.append(part)
    listing=d/'parts.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in parts))
    update(j,progress=52,message='Unindo cortes e tratando o áudio…')
    # Audio normalization is applied once to the entire sequence; video is copied.
    ff(['-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-map','0:a:0','-c:v','copy',
        '-af','afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000','-c:a','aac','-b:a','160k',
        '-movflags','+faststart',str(d/'edited.mp4'),
        '-map','0:a:0','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(d/'voice.wav')])
    for p in parts:p.unlink(missing_ok=True)
    listing.unlink(missing_ok=True)

def restart_cut(cues,duration):
    words=[w for c in cues for w in c.get('words',[])]
    tokens=[re.sub(r'[^a-záéíóúâêôãõç]','',w['text'].lower()) for w in words]
    chosen=None
    for i,t in enumerate(tokens):
        if t not in ['errei','errou']:continue
        # Require an explicit first-person restart near the admission of error.
        if t!='errei':continue
        window=' '.join(tokens[i:i+14])
        match=re.search(r'\b(?:vou )?(?:começar|comecar|recomeçar|recomecar) (?:de novo|novamente|do zero)\b',window)
        if not match:continue
        end_idx=i+len(window[:match.end()].split())-1
        if end_idx>=len(words)-1 or words[end_idx]['end']-words[i]['start']>7:continue
        nxt=words[end_idx+1]
        cut=min(nxt['start'],max(words[end_idx]['end']+.02,nxt['start']-.18))
        if duration-cut>=1:chosen=cut
    return chosen

def remove_abandoned_take(j,cues):
    d=DATA/j;duration=jobs[j]['edited_seconds'];cut=restart_cut(cues,duration)
    if cut is None:return cues
    update(j,progress=72,message='Removendo a tentativa anterior ao aviso de recomeço…')
    # The explicit “errei ... começar de novo” means a new full take. Preserve
    # the source upload; this optional rule never guesses an unannounced error.
    ff(['-ss',str(cut),'-i',str(d/'edited.mp4'),'-map','0:v:0','-map','0:a:0','-c:v','libx264','-threads','1','-preset','ultrafast','-tune','zerolatency','-crf','18','-c:a','aac','-b:a','160k','-movflags','+faststart',str(d/'retake.mp4')])
    ff(['-ss',str(cut),'-i',str(d/'voice.wav'),'-c:a','pcm_s16le',str(d/'retake.wav')])
    os.replace(d/'retake.mp4',d/'edited.mp4');os.replace(d/'retake.wav',d/'voice.wav')
    new_duration=float(probe(d/'edited.mp4')['format']['duration']);adjusted=[]
    for cue in cues:
        remaining=[w for w in cue.get('words',[]) if w['start']>=cut-.01]
        if not remaining:continue
        start=max(0,remaining[0]['start']-cut);end=min(new_duration,remaining[-1]['end']-cut)
        if end>start:adjusted.append({'start':start,'end':end,'text':' '.join(w['text'] for w in remaining)})
    if not adjusted:raise ValueError('Não foi possível confirmar a fala após o aviso de recomeço. Reenvie com a detecção de recomeços desativada.')
    update(j,edited_seconds=new_duration,retake_removed_seconds=cut)
    return adjusted

def job_transcribe(j):
    update(j,status='processing',progress=60,message='Transcrevendo em português com o modelo mais preciso…')
    hint=jobs[j].get('options',{}).get('transcription_hint','')
    return json.loads(run([sys.executable,str(ROOT/'transcribe_task.py'),str(DATA/j/'voice.wav'),hint])[0])

def prepare_export(j,cues):
    try:
        options=EditOptions(**jobs[j].get('options',{}))
        if not cues and (options.subtitles or options.zoom=='auto'):
            cues=job_transcribe(j)
            update(j,captions=cues)
        render(j,cues)
    except Exception as e:fail(j,e)

def process(j,review):
    d=DATA/j; source=d/'input'
    try:
        update(j,status='processing',progress=10,message='Analisando vídeo e pausas…')
        meta=probe(source); streams=meta['streams']; duration=float(meta['format']['duration'])
        if not math.isfinite(duration) or not 0<duration<=600: raise ValueError('Envie um vídeo com até 10 minutos.')
        if not any(s['codec_type']=='video' for s in streams) or not any(s['codec_type']=='audio' for s in streams): raise ValueError('O arquivo precisa conter vídeo e áudio.')
        if not any(x in meta['format']['format_name'].split(',') for x in ['mov','mp4']): raise ValueError('O conteúdo do arquivo não é MP4 ou MOV.')
        video_stream=next(stream for stream in streams if stream['codec_type']=='video')
        if video_stream.get('width',0)*video_stream.get('height',0)>4096*2304:
            raise ValueError('Este vídeo está acima de 4K. Exporte em 1080p ou 4K e envie novamente.')
        mode=jobs[j].get('options',{}).get('pause_mode','natural')
        threshold,_,_=pause_settings(mode)
        _,log=ff(['-i',str(source),'-vn','-af','silencedetect=noise=-35dB:d=0.12','-f','null','-'])
        keep=intervals(log,duration,mode,jobs[j].get('options',{}).get('trim_edges',True)); edited=sum(b-a for a,b in keep)
        update(j,original_seconds=duration,edited_seconds=edited,cuts=max(0,len(keep)-1),progress=25,message='Removendo pausas e tratando áudio…')
        cut_video(j,source,d,keep)
        update(j,edited_seconds=float(probe(d/'edited.mp4')['format']['duration']),media_ready=True)
        zoom_moments([],jobs[j]['edited_seconds'],EditOptions(**jobs[j].get('options',{})))
        options=EditOptions(**jobs[j].get('options',{}))
        cues=job_transcribe(j) if options.subtitles or options.zoom=='auto' or options.remove_retakes else []
        if options.remove_retakes:
            cues=remove_abandoned_take(j,cues)
        update(j,captions=cues)
        if review and options.subtitles: update(j,status='review',progress=75,message='Confira as legendas e clique em exportar.')
        else: render(j,cues)
    except Exception as e: fail(j,e)

async def cleaner():
    while True:
        await asyncio.sleep(60)
        with guard:
            expired=[j for j,v in jobs.items() if time.time()-v['created']>TTL and v['status'] not in ['processing','queued','exporting','uploading','cancelling']]
            for j in expired:
                shutil.rmtree(DATA/j,ignore_errors=True); del jobs[j]
                cancel_events.pop(j,None)

@asynccontextmanager
async def lifespan(app):
    # Runtime files do not survive a restart: no abandoned private uploads.
    for d in DATA.iterdir():
        if d.is_dir() and re.fullmatch('[a-f0-9]{48}',d.name): shutil.rmtree(d)
    t=asyncio.create_task(cleaner())
    yield
    with guard:
        for event in cancel_events.values(): event.set()
        for proc in active_processes.values(): stop_process(proc)
    t.cancel()
    with contextlib.suppress(asyncio.CancelledError): await t

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None)

@app.middleware('http')
async def security(request,call_next):
    password=os.getenv('JG_PASSWORD')
    if password:
        auth=request.headers.get('authorization','')
        try:
            supplied=base64.b64decode(auth.split(' ',1)[1],validate=True).decode().split(':',1)[1] if auth.startswith('Basic ') else ''
        except (ValueError,IndexError,UnicodeError): supplied=''
        if not secrets.compare_digest(supplied.encode(),password.encode()):
            return __import__('starlette.responses',fromlist=['Response']).Response('Entre com seu usuário e senha do estúdio.',401,headers={'WWW-Authenticate':'Basic realm="JG Reels AI", charset="UTF-8"'})
    # Reject cross-origin writes and DNS rebinding. Default is private/local.
    allowed=os.getenv('JG_HOSTS','localhost,127.0.0.1,testserver').split(',')
    if os.getenv('RENDER_EXTERNAL_HOSTNAME'): allowed.append(os.environ['RENDER_EXTERNAL_HOSTNAME'])
    host=request.url.hostname
    if host not in allowed: return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'Host não autorizado.'},400)
    origin=request.headers.get('origin')
    if request.method not in ['GET','HEAD'] and origin and origin not in [str(request.base_url).rstrip('/'),'https://'+request.headers.get('host','')]:
        return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'Origem não autorizada.'},403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'; response.headers['X-Content-Type-Options']='nosniff'; response.headers['Referrer-Policy']='no-referrer'
    return response

@app.get('/api/health')
def health(): return {'ffmpeg':bool(shutil.which('ffmpeg')),'transcription':'Whisper local','retention_hours':24}

@app.post('/api/jobs')
async def upload(request:Request,review:bool=False,resolution:Literal['1080','720','2160']='1080',format:Literal['reels','story','feed','square']='reels',framing:Literal['contain','cover']='contain',options:str='{}'):
    if request.headers.get('x-file-ext','').lower() not in ['mp4','mov']: raise HTTPException(415,'Use MP4 ou MOV.')
    try: edit_options=EditOptions.model_validate_json(options)
    except ValueError: raise HTTPException(422,'Ajustes de edição inválidos.')
    width,height=output_size(resolution,format)
    with guard:
        if sum(x['status'] in ['uploading','queued','processing','exporting'] for x in jobs.values())>=2: raise HTTPException(429,'A fila está cheia. Aguarde a edição atual.')
        if len(jobs)>=10: raise HTTPException(429,'Limite de arquivos temporários atingido. Exclua um projeto.')
        j=secrets.token_hex(24); cancel_events[j]=threading.Event(); jobs[j]={'id':j,'created':time.time(),'status':'uploading','progress':0,'message':'Recebendo vídeo…','captions':[],'resolution':resolution,'width':width,'height':height,'format':format,'framing':framing,'options':edit_options.model_dump()}
    d=DATA/j; d.mkdir(mode=0o700); size=0
    try:
        with (d/'input').open('wb') as out:
            async for chunk in request.stream():
                size+=len(chunk)
                if size>MAX_BYTES: raise HTTPException(413,'O limite é 300 MB.')
                out.write(chunk)
        if size<1000: raise HTTPException(400,'Arquivo vazio ou inválido.')
        update(j,status='queued',message='Aguardando processamento…')
        with guard: job_futures[j]=pool.submit(execute_job,j,process,review)
        return {'id':j}
    except BaseException:
        with guard: jobs.pop(j,None); cancel_events.pop(j,None)
        shutil.rmtree(d,ignore_errors=True); raise

@app.post('/api/jobs/{j}/cancel')
def cancel(j:str):
    with guard:
        job=get(j)
        if job['status'] in ['cancelled','cancelling']: return {'status':job['status']}
        if job['status'] not in ['queued','processing','exporting']:
            raise HTTPException(409,'Este processamento já terminou. Atualize o resultado.')
        cancel_events[j].set()
        jobs[j].update(status='cancelling',message='Cancelando processamento…')
        future=job_futures.get(j)
        queued_cancelled=future is not None and future.cancel()
        proc=active_processes.get(j)
        if proc: stop_process(proc)
        if queued_cancelled:
            job_futures.pop(j,None); finish_cancel(j)
        return {'status':jobs[j]['status']}

@app.get('/api/jobs/{j}')
def status(j:str):
    job=get(j)
    job['can_export']=job['status'] in ['review','done'] or (job['status']=='error' and job.get('media_ready',False))
    if job.get('edited_seconds') and job.get('captions'):
        job['suggested_zoom']=zoom_moments(job['captions'],job['edited_seconds'],EditOptions(zoom='auto'))
    else:job['suggested_zoom']=[]
    return job

class Cue(BaseModel):
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)
    text:str=Field(min_length=1,max_length=160)
class Export(BaseModel):
    captions:list[Cue]=Field(default_factory=list,max_length=2500)
    options:EditOptions|None=None

@app.post('/api/jobs/{j}/export')
def export(j:str,body:Export):
    with guard:
        job=get(j)
        if job['status'] not in ['review','done'] and not (job['status']=='error' and job.get('media_ready')): raise HTTPException(409,'Aguarde o processamento.')
        previous=0
        for c in body.captions:
            if c.end<=c.start or c.start<previous or c.end>job['edited_seconds']+0.15: raise HTTPException(422,'Tempos de legenda inválidos.')
            previous=c.end
        options=body.options or EditOptions(**job.get('options',{}))
        options=options.model_copy(update={'pause_mode':job.get('options',{}).get('pause_mode','natural'),'transcription_hint':job.get('options',{}).get('transcription_hint',''),'trim_edges':job.get('options',{}).get('trim_edges',True),'remove_retakes':job.get('options',{}).get('remove_retakes',True)})
        try: zoom_moments([c.model_dump() for c in body.captions],job['edited_seconds'],options)
        except ValueError as e: raise HTTPException(422,str(e))
        update(j,status='queued',message='Exportação na fila…',options=options.model_dump())
    with guard: job_futures[j]=pool.submit(execute_job,j,prepare_export,[c.model_dump() for c in body.captions])
    return {'ok':True}

@app.get('/api/jobs/{j}/video')
def video(j:str,download:bool=False,preview:bool=False):
    job=get(j)
    if preview:
        if job['status'] not in ['review','done'] and not (job['status']=='error' and job.get('media_ready')): raise HTTPException(409,'Prévia ainda indisponível.')
        p=DATA/j/'edited.mp4'
    else:
        if job['status']!='done': raise HTTPException(409,'Exportação ainda indisponível.')
        p=DATA/j/'final.mp4'
    return FileResponse(p,media_type='video/mp4',filename='JG-Reels-AI.mp4' if download else None)

@app.delete('/api/jobs/{j}')
def delete(j:str):
    with guard:
        job=get(j)
        if job['status'] in ['uploading','queued','processing','exporting','cancelling']: raise HTTPException(409,'Aguarde o processamento para excluir.')
        shutil.rmtree(DATA/j,ignore_errors=True); del jobs[j]; cancel_events.pop(j,None)
    return {'ok':True}

app.mount('/',StaticFiles(directory=ROOT/'static',html=True),name='interface')
