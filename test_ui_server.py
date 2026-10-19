"""Only for test_ui.cjs: temporary local server with a known transcript."""
import os,tempfile,json
os.environ['JG_DATA']=tempfile.mkdtemp(prefix='jg-ui-fixture-')
import app,uvicorn
original=app.run
def fixture(args,timeout=1800):
    if len(args)>1 and args[1].endswith('transcribe_task.py'):
        return json.dumps([{'start':.3,'end':1.6,'text':'Uma frase comum sobre o cotidiano.'},{'start':2.5,'end':3.5,'text':'Outra frase segue tranquila.'}]),''
    return original(args,timeout)
app.run=fixture
if __name__=='__main__':uvicorn.run(app.app,host='127.0.0.1',port=8012,log_level='warning')
