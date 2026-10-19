import io,json,os,unittest,urllib.error
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app import app
import marketing_ai as m
FIXTURE={'angle':'Documentação antes de negociar o arrendamento','hook_reason':'Uma pergunta concreta sobre organização documental','cta':'Salve para organizar sua próxima leitura.','slides':[{'title':'Antes de arrendar, o que conferir?','body':'Organize documentos e dúvidas antes de negociar.'}], 'caption':'Uma negociação começa com informações organizadas. Confira o contexto do contrato.','hashtags':['#DireitoAgrario','#ArrendamentoRural','#DireitoRural'],'visual':{'theme':'paper','font':'serif','align':'center','accent':'#946344'},'reference_observations':[],'verification_notes':['As cláusulas específicas precisam ser conferidas no contrato.']}
ENV={'GEMINI_API_KEY':'test-placeholder-not-a-real-key','JG_MARKETING_AI_ENABLED':'true','JG_GEMINI_FREE_PROJECT_CONFIRMED':'true'}
BRIEF={'idea':'Cuidados com o arrendamento rural','audience':'Produtores rurais','format':'story','consent':True}
class Tests(unittest.TestCase):
 def setUp(self):m.usage.update(day='',calls=0,last=0)
 def test_disabled_and_no_secret_in_status(self):
  with patch.dict(os.environ,{'GEMINI_API_KEY':''},clear=False),TestClient(app) as c,patch.object(m,'provider') as p:
   d=c.get('/api/publications/ai/status').json();self.assertFalse(d['configured']);self.assertNotIn('API_KEY',str(d));self.assertEqual(c.post('/api/publications/ai/generate',json=BRIEF).status_code,503);p.assert_not_called()
 def test_consent_limits_and_valid_pipeline(self):
  with patch.dict(os.environ,ENV),TestClient(app) as c,patch.object(m,'provider',return_value=m.Output(**FIXTURE)) as p:
   self.assertEqual(c.post('/api/publications/ai/generate',json={**BRIEF,'consent':False}).status_code,422)
   r=c.post('/api/publications/ai/generate',json=BRIEF);self.assertEqual(r.status_code,200);self.assertEqual(r.json()['result']['slides'][0]['title'],FIXTURE['slides'][0]['title']);p.assert_called_once()
   self.assertEqual(c.post('/api/publications/ai/generate',json=BRIEF).status_code,429)
   self.assertEqual(c.post('/api/publications/ai/generate',content=b'x'*2100001).status_code,413)
 def test_images_require_separate_consent(self):
  import base64
  data=base64.b64encode(b'\xff\xd8\xff'+b'fixture').decode()
  with patch.dict(os.environ,ENV),TestClient(app) as c,patch.object(m,'provider') as p:
   self.assertEqual(c.post('/api/publications/ai/generate',json={**BRIEF,'references':[{'data':data}]}).status_code,422);p.assert_not_called()
   self.assertEqual(c.post('/api/publications/ai/generate',json={**BRIEF,'references':[{'data':'notbase64'}],'image_consent':True}).status_code,422)
 def test_real_request_serialization_and_response_validation(self):
  envelope={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(FIXTURE)}]}}]}
  class Opener:
   def open(inner,request,timeout):
    self.assertEqual(request.full_url,'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent');self.assertNotIn(ENV['GEMINI_API_KEY'],request.full_url);payload=json.loads(request.data);self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json');self.assertNotIn('tools',payload);self.assertIn('não tem navegação',payload['systemInstruction']['parts'][0]['text']);return io.BytesIO(json.dumps(envelope).encode())
  with patch.dict(os.environ,ENV),patch.object(m.urllib.request,'build_opener',return_value=Opener()):
   result=m.provider(m.Input(**BRIEF));self.assertEqual(len(result.slides),1)
   envelope['candidates'][0]['finishReason']='MAX_TOKENS'
   with self.assertRaises(HTTPException) as e:m.provider(m.Input(**BRIEF))
   self.assertEqual(e.exception.status_code,502)
 def test_hashtags_normalized(self):
  fixture={**FIXTURE,'hashtags':['DireitoAgrario','#DireitoRural','DireitoAgrario']}
  self.assertEqual(m.Output(**fixture).hashtags,['#DireitoAgrario','#DireitoRural'])
 def test_provider_quota_and_network_errors_are_clear(self):
  class Opener:
   def open(self,*a,**k):raise urllib.error.HTTPError('https://generativelanguage.googleapis.com/',429,'quota',{},None)
  with patch.dict(os.environ,ENV),patch.object(m.urllib.request,'build_opener',return_value=Opener()):
   with self.assertRaises(HTTPException) as e:m.provider(m.Input(**BRIEF))
   self.assertEqual(e.exception.status_code,429)
if __name__=='__main__':unittest.main()
