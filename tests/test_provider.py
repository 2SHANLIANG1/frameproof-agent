import base64
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image

from qc.provider import VisionProvider, local_ollama_base, provider_status, output_schema


@pytest.mark.parametrize('url', ['http://192.168.1.2:11434', 'http://127.0.0.1.example.com:11434',
    'http://user:secret@localhost:11434', 'http://localhost:11434/api',
    'http://localhost:11434?redirect=x', 'file:///tmp/model'])
def test_ollama_requires_loopback(monkeypatch,url):
    monkeypatch.setenv('QC_OLLAMA_BASE',url)
    with pytest.raises(ValueError): local_ollama_base()


@pytest.mark.parametrize('url', ['http://127.0.0.1:11434', 'http://localhost:11434/', 'http://[::1]:11434'])
def test_loopback_urls(monkeypatch,url):
    monkeypatch.setenv('QC_OLLAMA_BASE',url)
    assert local_ollama_base()==url.rstrip('/')


def test_remote_http_still_rejected(monkeypatch):
    for key,value in {'QC_PROVIDER':'openai_compatible','QC_ENABLE_LIVE':'1','QC_MODEL':'vision',
                      'QC_API_BASE':'http://example.com/v1','QC_API_KEY':'test'}.items():
        monkeypatch.setenv(key,value)
    with pytest.raises(ValueError): VisionProvider()


def test_probe_schema_keeps_shot_identity_and_task_scope():
    schema=output_schema('probe',{'image_labels':['Shot #2','Shot #4'],
                                  'task':{'task_type':'consistency'}})
    finding=schema['properties']['findings']['items']['properties']
    assert finding['shot_id']['enum']==['Shot #2','Shot #4']
    assert 'prompt_deviation' not in finding['defect_type']['enum']
    assert schema['properties']['entity_verdicts']['items']['properties']['shot_id']==finding['shot_id']


def test_cloud_credentials_never_exposed_in_health(monkeypatch):
    monkeypatch.setenv('QC_PROVIDER','openai_compatible')
    monkeypatch.setenv('QC_ENABLE_LIVE','1')
    monkeypatch.setenv('QC_MODEL','vision')
    monkeypatch.setenv('QC_API_BASE','https://provider.example/v1')
    monkeypatch.setenv('QC_API_KEY','private-test-key')
    status=provider_status()
    assert status['live_ready']
    assert 'private-test-key' not in json.dumps(status)


def test_thinking_only_response_explains_correct_model(monkeypatch):
    for key,value in {'QC_PROVIDER':'ollama','QC_ENABLE_LIVE':'1','QC_MODEL':'custom-thinking:8b',
                      'QC_OLLAMA_BASE':'http://127.0.0.1:11434'}.items():
        monkeypatch.setenv(key,value)
    provider=VisionProvider()
    class Opener:
        def open(self,*args,**kwargs):
            return io.StringIO(json.dumps({'message':{'content':'','thinking':'private reasoning'},
                                           'done_reason':'length','eval_count':1800}))
    provider.opener=Opener()
    with pytest.raises(ValueError,match='8b-instruct') as caught:
        provider.ask('planner','Return JSON.',{})
    assert 'private reasoning' not in str(caught.value)


def test_qwen_vl_default_tag_requires_instruct_variant(monkeypatch):
    for key,value in {'QC_PROVIDER':'ollama','QC_ENABLE_LIVE':'1','QC_MODEL':'qwen3-vl:8b',
                      'QC_OLLAMA_BASE':'http://127.0.0.1:11434'}.items():
        monkeypatch.setenv(key,value)
    status=provider_status()
    assert not status['live_ready']
    assert '8b-instruct' in status['detail']
    with pytest.raises(ValueError): VisionProvider()


def test_native_ollama_image_json_and_usage(monkeypatch):
    observed=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'models':[{'name':'test-vl:8b'}]}).encode())
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            observed.append((self.path,body,self.headers.get('Authorization')))
            response={'message':{'content':json.dumps({'sketch':'coat is blue'})},
                      'prompt_eval_count':70,'eval_count':12}
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(response).encode())
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        for key,value in {'QC_PROVIDER':'ollama','QC_ENABLE_LIVE':'1','QC_MODEL':'test-vl:8b',
                          'QC_OLLAMA_BASE':f'http://127.0.0.1:{http.server_port}'}.items():
            monkeypatch.setenv(key,value)
        monkeypatch.delenv('QC_API_KEY',raising=False)
        assert provider_status(check_connection=True)['live_ready']
        provider=VisionProvider()
        image=Image.new('RGB',(16,16),'blue')
        output=provider.ask('shot_selector','Read image.',{},[('Shot #1',image)])
        assert output['sketch']=='coat is blue'
        path,body,auth=observed[0]
        assert path=='/api/chat' and auth is None
        assert body['think'] is False and body['stream'] is False
        assert body['format']['required']==['sketch']
        decoded=Image.open(io.BytesIO(base64.b64decode(body['messages'][2]['images'][0])))
        assert decoded.size==(16,16)
        assert provider.logs[0]['tokens_in']==70 and provider.logs[0]['tokens_out']==12
        assert provider.logs[0]['model']=='test-vl:8b'
        monkeypatch.setenv('QC_MODEL','missing')
        assert not provider_status(check_connection=True)['live_ready']
    finally:
        http.shutdown();thread.join()
