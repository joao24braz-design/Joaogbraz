"""JG Reels AI: single-user local service. No paid APIs."""
import signal, sys, asyncio, base64, contextlib, json, logging, math, os, re, secrets, shutil, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).parent
DATA=Path(os.getenv('JG_DATA',str(ROOT/'data'))).resolve(); DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
MAX_BYTES=300*1024*1024; TTL=24*3600
jobs={}; guard=threading.RLock(); pool=ThreadPoolExecutor(max_workers=1)
model=None

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

def intervals(log,duration):
    gaps=[]; start=None
    for kind,value in re.findall(r'silence_(start|end):\s*([\d.]+)',log):
        if kind=='start': start=float(value)
        elif start is not None: gaps.append((start,min(duration,float(value)))); start=None
    if start is not None: gaps.append((start,duration))
    keep=[]; pos=0
    for a,b in gaps:
        if b-a<0.6: continue
        left=min(duration,a+0.14); right=max(left,b-0.18)
        if left>pos+0.04: keep.append((pos,left))
        pos=max(pos,right)
    if duration-pos>0.04: keep.append((pos,duration))
    if sum(b-a for a,b in keep)<0.35: raise ValueError('Não foi detectada fala suficiente. Confira o áudio do vídeo.')
    if len(keep)>200: raise ValueError('Muitas pausas detectadas. Use um vídeo mais curto ou com menos ruído.')
    return keep

def stamp(t):
    cs=round(max(0,t)*100); return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def ass_file(path,cues):
    header='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Premium,DejaVu Sans,58,&H00F4F5F7,&H007DA9C4,&H00110F0B,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,2,100,190,370,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    lines=[]
    for c in cues:
        words=c['text'].replace('\\','').replace('{','').replace('}','').split()
        if not words: continue
        # Copper emphasis without guessing word timing; transcription supplies cue boundaries.
        words[-1]=r'{\c&H007DA9C4&}'+words[-1]+r'{\c&H00F4F5F7&}'
        text=' '.join(words)
        lines.append(f"Dialogue: 0,{stamp(c['start'])},{stamp(c['end'])},Premium,,0,0,0,,{{\\fad(70,70)}}{text}")
    path.write_text(header+'\n'.join(lines),encoding='utf-8')

def transcribe(audio):
    global model
    from faster_whisper import WhisperModel
    if model is None:
        model=WhisperModel(os.getenv('WHISPER_MODEL','base'),device='cpu',compute_type='int8',cpu_threads=2,download_root=os.getenv('WHISPER_CACHE',str(ROOT/'models')))
    import wave
    import numpy as np
    with wave.open(str(audio),'rb') as source:
        samples=np.frombuffer(source.readframes(source.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
    segments,_=model.transcribe(samples,language='pt',beam_size=3,word_timestamps=True,condition_on_previous_text=False)
    cues=[]
    for s in segments:
        words=[w for w in (s.words or []) if w.word.strip()]
        batch=[]
        for w in words:
            if batch and (len(batch)>=6 or w.end-batch[0].start>2.8 or len(' '.join(x.word for x in batch))+len(w.word)>44):
                cues.append({'start':batch[0].start,'end':batch[-1].end,'text':' '.join(x.word.strip() for x in batch)}); batch=[]
            batch.append(w)
        if batch: cues.append({'start':batch[0].start,'end':batch[-1].end,'text':' '.join(x.word.strip() for x in batch)})
    if not cues: raise ValueError('A transcrição não reconheceu fala. Confira o áudio e tente novamente.')
    return cues

def render(j,cues):
    d=DATA/j
    try:
        update(j,status='exporting',progress=85,message='Incorporando legendas e exportando MP4…')
        ass_file(d/'captions.ass',cues)
        ff(['-i',str(d/'edited.mp4'),'-vf',f"ass=filename='{d/'captions.ass'}'",'-c:v','libx264','-threads','1','-preset','veryfast','-tune','zerolatency','-crf','21','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(d/'final.tmp.mp4')])
        os.replace(d/'final.tmp.mp4',d/'final.mp4')
        update(j,status='done',progress=100,message='Seu Reels está pronto.',captions=cues)
    except Exception as e: fail(j,e)

def fail(j,e):
    if isinstance(e,JobCancelled) or (cancel_events.get(j) and cancel_events[j].is_set()): return
    logging.exception('Job %s failed',j)
    msg=str(e) if isinstance(e,ValueError) else 'Processamento interrompido. Verifique FFmpeg, memória e acesso ao modelo Whisper. Consulte o registro do servidor.'
    update(j,status='error',message=msg,progress=0)

def cut_video(j,source,d,keep):
    # Bound decoder/encoder queues: never keep all trimmed source branches in RAM.
    parts=[]
    for i,(a,b) in enumerate(keep):
        update(j,progress=25+int(25*i/len(keep)),message=f'Cortando trecho {i+1} de {len(keep)}…')
        part=d/f'part-{i:03d}.mkv'
        ff(['-ss',str(a),'-i',str(source),'-t',str(b-a),'-map','0:v:0','-map','0:a:0',
            '-vf','scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x091715,setsar=1,fps=30',
            '-af','aresample=48000','-ac','2','-c:v','libx264','-threads','1','-preset','ultrafast','-tune','zerolatency',
            '-crf','18','-pix_fmt','yuv420p','-c:a','pcm_s16le','-avoid_negative_ts','make_zero',str(part)])
        parts.append(part)
    listing=d/'parts.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in parts))
    update(j,progress=52,message='Unindo cortes e tratando o áudio…')
    # Audio normalization is applied once to the entire sequence; video is copied.
    ff(['-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-map','0:a:0','-c:v','copy',
        '-af','afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000','-c:a','aac','-b:a','160k',
        '-movflags','+faststart',str(d/'edited.mp4')])
    for p in parts:p.unlink(missing_ok=True)
    listing.unlink(missing_ok=True)

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
        _,log=ff(['-i',str(source),'-vn','-af','silencedetect=noise=-35dB:d=0.6','-f','null','-'])
        keep=intervals(log,duration); edited=sum(b-a for a,b in keep)
        update(j,original_seconds=duration,edited_seconds=edited,cuts=max(0,len(keep)-1),progress=25,message='Removendo pausas e tratando áudio…')
        cut_video(j,source,d,keep)
        update(j,edited_seconds=float(probe(d/'edited.mp4')['format']['duration']))
        update(j,progress=60,message='Transcrevendo a fala em português…')
        ff(['-i',str(d/'edited.mp4'),'-vn','-ac','1','-ar','16000',str(d/'voice.wav')])
        cues=json.loads(run([sys.executable,str(ROOT/'transcribe_task.py'),str(d/'voice.wav')])[0])
        update(j,captions=cues)
        if review: update(j,status='review',progress=75,message='Confira as legendas e clique em exportar.')
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
async def upload(request:Request,review:bool=False):
    if request.headers.get('x-file-ext','').lower() not in ['mp4','mov']: raise HTTPException(415,'Use MP4 ou MOV.')
    with guard:
        if sum(x['status'] in ['uploading','queued','processing','exporting'] for x in jobs.values())>=2: raise HTTPException(429,'A fila está cheia. Aguarde a edição atual.')
        if len(jobs)>=10: raise HTTPException(429,'Limite de arquivos temporários atingido. Exclua um projeto.')
        j=secrets.token_hex(24); cancel_events[j]=threading.Event(); jobs[j]={'id':j,'created':time.time(),'status':'uploading','progress':0,'message':'Recebendo vídeo…','captions':[]}
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
def status(j:str): return get(j)

class Cue(BaseModel):
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)
    text:str=Field(min_length=1,max_length=160)
class Export(BaseModel): captions:list[Cue]=Field(min_length=1,max_length=2500)

@app.post('/api/jobs/{j}/export')
def export(j:str,body:Export):
    with guard:
        job=get(j)
        if job['status'] not in ['review','done']: raise HTTPException(409,'Aguarde o processamento.')
        previous=0
        for c in body.captions:
            if c.end<=c.start or c.start<previous or c.end>job['edited_seconds']+0.15: raise HTTPException(422,'Tempos de legenda inválidos.')
            previous=c.end
        update(j,status='queued',message='Exportação na fila…')
    with guard: job_futures[j]=pool.submit(execute_job,j,render,[c.model_dump() for c in body.captions])
    return {'ok':True}

@app.get('/api/jobs/{j}/video')
def video(j:str,download:bool=False,preview:bool=False):
    job=get(j)
    if preview:
        if job['status'] not in ['review','done']: raise HTTPException(409,'Prévia ainda indisponível.')
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
