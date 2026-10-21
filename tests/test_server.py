import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import server
from qc.media import create_fixtures


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    original = server.DATA
    server.DATA = tmp_path_factory.mktemp('http')
    create_fixtures(server.DATA/'fixtures')
    http = ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread = threading.Thread(target=http.serve_forever,daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{http.server_port}'
    def request(path, data=None, headers=None, raw=False):
        encoded = data if raw else json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(base+path,data=encoded,
            headers={'X-FrameProof':'1',**(headers or {})})
        try:
            with urllib.request.urlopen(req,timeout=60) as response:
                return response.status,response.read(),dict(response.headers)
        except urllib.error.HTTPError as error:
            return error.code,error.read(),dict(error.headers)
    yield request
    http.shutdown()
    thread.join()
    server.DATA = original


def test_health_and_range(client):
    assert json.loads(client('/api/health')[1])['status']=='ok'
    status,body,headers=client('/media/drift/video.mp4',headers={'Range':'bytes=0-31'})
    assert status==206 and len(body)==32 and headers['Content-Range'].startswith('bytes 0-31/')
    assert client('/artifacts/../../.env')[0]==404


def test_bundled_example_has_prompt_and_serves_video(client):
    videos = json.loads(client('/api/videos')[1])
    example = next(v for v in videos if v.get('default_example'))
    assert example['video_id'] == 'underwater'
    assert example['synthetic'] is False
    assert '深海潜水员' in example['prompt']
    status, body, headers = client('/media/underwater/video.mp4', headers={'Range':'bytes=0-31'})
    assert status == 206 and len(body) == 32
    assert client('/media/underwater/poster.jpg')[0] == 200


def test_foreign_origin_rejected(client):
    assert client('/api/runs',{'video_id':'drift'},headers={'Origin':'https://foreign.example'})[0]==403


def test_vue_build_assets_and_traversal(client):
    import re
    status, body, _ = client('/')
    assert status == 200 and b'id="app"' in body
    assets = re.findall(rb'(?:src|href)="(/assets/[^" ]+)"', body)
    assert len(assets) >= 2
    for asset in assets:
        status, content, headers = client(asset.decode())
        assert status == 200 and content
        assert ('javascript' if asset.endswith(b'.js') else 'text/css') in headers['Content-Type']
    assert client('/assets/%2e%2e/%2e%2e/.env')[0] == 404
    assert client('/assets/../../server.py')[0] == 404
    assert client('/assets/missing.js')[0] == 404


def test_upload_run_export_and_feedback(client):
    source=(server.DATA/'fixtures'/'drift'/'video.mp4').read_bytes()
    status,body,_=client('/api/upload',source,raw=True)
    assert status==201
    uploaded=json.loads(body)
    assert uploaded['synthetic'] is False
    assert uploaded['segmentation']=='equal_duration_heuristic'
    status,body,_=client('/api/runs',{'video_id':uploaded['video_id']})
    assert status==202
    job_id=json.loads(body)['id']
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        job=json.loads(client('/api/runs/'+job_id)[1])
        if job['status']!='running': break
        time.sleep(.1)
    assert job['status']=='done'
    assert job['report']['status']=='needs_review'
    assert client('/artifacts/'+job_id+'/report.json')[0]==200
    assert client('/api/feedback',{'run_id':job_id,'note':'Needs semantic review'})[0]==201


def test_invalid_metadata_returns_client_error(client):
    assert client('/api/runs',{'video_id':'drift','metadata':{'shot_table':[]}})[0]==400
    assert client('/api/runs',{'video_id':'../../outside'})[0]==400
