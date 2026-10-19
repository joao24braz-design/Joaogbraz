import io,json,subprocess,tempfile,unittest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from app import app,jobs,publication_reel_lock
class ReelTest(unittest.TestCase):
 def test_export_real_and_validation(self):
  image=Image.new('RGB',(1080,1920),'#103c36');buffer=io.BytesIO();image.save(buffer,format='PNG');png=buffer.getvalue()
  with TestClient(app) as c:
   self.assertEqual(c.post('/api/publications/reel',content=png).status_code,415)
   self.assertEqual(c.post('/api/publications/reel',content=b'bad',headers={'Content-Type':'image/png'}).status_code,422)
   self.assertEqual(c.post('/api/publications/reel',content=b'x'*(10*1024*1024+1),headers={'Content-Type':'image/png'}).status_code,413)
   publication_reel_lock.acquire()
   try:self.assertEqual(c.post('/api/publications/reel',content=png,headers={'Content-Type':'image/png'}).status_code,429)
   finally:publication_reel_lock.release()
   jobs['test-active']={'status':'processing','created':0}
   try:self.assertEqual(c.post('/api/publications/reel',content=png,headers={'Content-Type':'image/png'}).status_code,409)
   finally:jobs.pop('test-active')
   r=c.post('/api/publications/reel',content=png,headers={'Content-Type':'image/png'});self.assertEqual(r.status_code,200);self.assertEqual(r.headers['content-type'],'video/mp4')
   with tempfile.TemporaryDirectory() as folder:
    file=Path(folder)/'reel.mp4';file.write_bytes(r.content)
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(file)]));v=data['streams'][0]
    self.assertEqual((v['codec_name'],v['width'],v['height'],v['pix_fmt']),('h264',1080,1920,'yuv420p'));self.assertAlmostEqual(float(data['format']['duration']),8,places=1)
    subprocess.run(['ffmpeg','-v','error','-i',str(file),'-f','null','-'],check=True)
if __name__=='__main__':unittest.main()
