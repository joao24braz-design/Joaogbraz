import json,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
import publications as p
from app import app

class ResearchTests(unittest.TestCase):
 def setUp(self):p.cache.clear()
 def test_validation_and_untrusted_urls(self):
  for url in ['http://www.gov.br/','https://www.gov.br.evil.test/','https://user@www.gov.br/','https://127.0.0.1/','https://www.gov.br:444/']:self.assertFalse(p.allowed(url))
  self.assertTrue(p.allowed('https://www.gov.br/incra'))
  self.assertEqual(p.plain('<script>bad</script><p>Título &amp; tema</p>'),'Título & tema')
 def test_dates_dedup_partial_failure_and_cache(self):
  now=datetime.now(timezone.utc).isoformat();url='https://www.gov.br/incra/tema'
  def read(source):
   if source[0]=='STJ':return [],dict(source='STJ',ok=False,count=0)
   return [dict(title='Crédito rural em pauta',url=url,date=now,summary='Informações públicas',source=source[0]),dict(title='Antiga agricultura',url=url+'/old',date='2020-01-01T00:00:00Z',summary='',source=source[0])],dict(source=source[0],ok=True,count=2)
  with patch.object(p,'read_source',side_effect=read) as mocked:
   with TestClient(app) as c:
    r=c.get('/api/publications/research?q=crédito&days=7');self.assertEqual(r.status_code,200);d=r.json();self.assertEqual(len(d['items']),1);self.assertTrue(d['items'][0]['today']);self.assertEqual(sum(s['ok'] for s in d['sources']),3)
    self.assertTrue(c.get('/api/publications/research?q=crédito&days=7').json()['cached']);self.assertEqual(mocked.call_count,4)
    self.assertEqual(c.get('/api/publications/research?days=100').status_code,422)
 def test_rss_json_and_failure(self):
  rss='<rss><channel><item><title>Contrato rural</title><link>https://www.stj.jus.br/test</link><pubDate>Mon, 19 Oct 2026 12:00:00 GMT</pubDate><description>&lt;b&gt;Tema&lt;/b&gt;</description></item></channel></rss>'
  with patch.object(p,'fetch',return_value=rss):
   rows,s=p.read_source(('Teste','https://www.stj.jus.br/rss','rss'));self.assertEqual(rows[0]['summary'],'Tema');self.assertTrue(s['ok'])
  raw=json.dumps({'items':[{'title':'Imóvel rural','@id':'https://www.gov.br/incra/test','effective':'2026-10-19T12:00:00Z','description':'Tema'}]})
  with patch.object(p,'fetch',return_value=raw):self.assertEqual(len(p.read_source(p.SOURCES[0])[0]),1)
  with patch.object(p,'fetch',side_effect=OSError()):self.assertFalse(p.read_source(p.SOURCES[0])[1]['ok'])
if __name__=='__main__':unittest.main()
