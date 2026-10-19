"""Bounded, read-only research of public official sources; no paid/AI APIs."""
import json,re,time,threading,unicodedata,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Query,HTTPException
router=APIRouter();cache={};cache_guard=threading.Lock();research_guard=threading.Lock()
SOURCES=[('Incra','https://www.gov.br/incra/++api++/pt-br/assuntos/noticias/@search?portal_type=News%20Item&sort_on=effective&sort_order=descending&b_size=30&metadata_fields=effective','json'),('Câmara · Agropecuária','https://www.camara.leg.br/noticias/rss/dinamico/AGROPECUARIA','rss'),('Câmara · Meio Ambiente','https://www.camara.leg.br/noticias/rss/dinamico/MEIO-AMBIENTE','rss'),('STJ','https://res.stj.jus.br/hrestp-c-portalp/RSS.xml','rss')]
HOSTS={'www.gov.br','www.camara.leg.br','www.stj.jus.br','res.stj.jus.br'}
def allowed(url):
 p=urllib.parse.urlsplit(url)
 return p.scheme=='https' and p.hostname in HOSTS and not p.username and not p.password and p.port in (None,443)
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not allowed(newurl):raise ValueError('Redirecionamento fora das fontes oficiais.')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url):
 if not allowed(url):raise ValueError('Fonte não permitida.')
 request=urllib.request.Request(url,headers={'User-Agent':'JGReelsResearch/1.0 (+public official news reader)','Accept':'application/json,application/xml,text/html;q=0.8'})
 with urllib.request.build_opener(Redirect()).open(request,timeout=10) as r:
  if r.headers.get('Content-Encoding') not in (None,'identity'):raise ValueError('Formato de resposta não suportado.')
  raw=r.read(2_000_001)
  if len(raw)>2_000_000:raise ValueError('Resposta excedeu o limite.')
  return raw.decode('utf-8',errors='replace')
class Text(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style'):self.skip+=1
  if tag in ('p','br','div','li'):self.parts.append(' ')
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.skip=max(0,self.skip-1)
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
def plain(s):
 p=Text();p.feed(s or '');return re.sub(r'\s+',' ',''.join(p.parts)).strip()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
def date(s):
 try:
  d=datetime.fromisoformat(s.replace('Z','+00:00'))
 except (ValueError,AttributeError):
  try:d=parsedate_to_datetime(s)
  except (ValueError,TypeError,AttributeError):return None
 return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
TERMS=('agrari','rural','fundiari','arrendamento','agricult','agropec','assentamento','desapropri','usucapiao','reforma agr','produtor','credito rural',' cpr ','licenciamento ambiental','reserva legal','codigo florestal',' georreferenc')
def relevant(text,query=''):
 s=norm(' '+text+' ')
 return any(t in s for t in TERMS) and (not query or all(w in s for w in norm(query).split() if len(w)>2))
def read_source(source):
 name,url,kind=source
 try:
  raw=fetch(url);items=[]
  if kind=='json':
   for x in json.loads(raw).get('items',[]):items.append((x.get('title',''),x.get('@id',''),x.get('effective',''),x.get('description','')))
  else:
   root=ET.fromstring(raw)
   for x in root.findall('.//item'):
    items.append((x.findtext('title',''),x.findtext('link',''),x.findtext('pubDate',''),x.findtext('description','')))
  clean=[]
  for title,link,published,summary in items:
   when=date(published)
   if not title or not allowed(link):continue
   clean.append(dict(title=plain(title)[:300],url=link,date=when.isoformat() if when else None,summary=plain(summary)[:380],source=name))
  return clean,dict(source=name,ok=True,count=len(clean))
 except Exception:return [],dict(source=name,ok=False,count=0,message='Canal indisponível ou formato alterado.')

def research(query='',days=30):
 key=(query,days)
 with cache_guard:
  hit=cache.get(key)
  if hit and time.time()-hit[0]<900:return {**hit[1],'cached':True}
 if not research_guard.acquire(blocking=False):raise HTTPException(429,'Uma pesquisa está em andamento. Aguarde alguns segundos e tente novamente.')
 try:
  now=datetime.now(timezone.utc);cutoff=now-timedelta(days=days);items=[];status=[]
  with ThreadPoolExecutor(max_workers=4) as pool:
   for rows,st in pool.map(read_source,SOURCES):items.extend(rows);status.append(st)
  found={}
  for row in items:
   when=date(row['date'])
   if when and cutoff<=when<=now+timedelta(hours=2) and relevant(row['title']+' '+row['summary'],query):found.setdefault(row['url'],row)
  results=sorted(found.values(),key=lambda x:x['date'],reverse=True)[:16]
  today=now.astimezone(ZoneInfo('America/Sao_Paulo')).date()
  for row in results:
   row['today']=date(row['date']).astimezone(ZoneInfo('America/Sao_Paulo')).date()==today
   row['checked_at']=now.isoformat()
  response={'items':results,'sources':status,'checked_at':now.isoformat(),'days':days,'cached':False,'notice':'Pesquisa de canais oficiais com filtro de relevância. Não é pesquisa exaustiva nem análise jurídica. Confira a íntegra, o estágio de projetos e a vigência de normas antes de publicar.'}
  with cache_guard:
   if len(cache)>20:cache.clear()
   cache[key]=(time.time(),response)
  return response
 finally:research_guard.release()
@router.get('/api/publications/research')
def search(q:str=Query(default='',max_length=100),days:int=Query(default=30,ge=1,le=90)):
 return research(q.strip(),days)
