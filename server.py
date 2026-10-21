"""Local-only HTTP server; stdlib runtime keeps the demo easy to inspect and deploy."""
import argparse
import json
import mimetypes
import os
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from qc.engine import run_inspection, validate_meta
from qc.media import create_fixtures, inspect_video
from qc.provider import provider_status
from qc.reporting import enrich_report

ROOT = Path(__file__).resolve().parent
DATA = ROOT/'data'
JOBS = {}
LOCK = threading.RLock()
ACTIVE = threading.BoundedSemaphore(1)


def load_env():
    path = ROOT/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def video_roots():
    return [ROOT/'examples', DATA/'fixtures', DATA/'uploads']


def get_meta(video_id):
    if not isinstance(video_id, str) or not video_id.replace('-', '').isalnum():
        raise ValueError('无效视频 ID')
    for parent in video_roots():
        path = parent/video_id/'meta.json'
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8')), path.parent/'video.mp4'
    raise ValueError('视频不存在')


def work(job_id, meta, path, mode, budget):
    def emit(event):
        with LOCK:
            JOBS[job_id]['events'].append(event)
    try:
        report = run_inspection(meta, path, DATA/'runs'/job_id, mode, budget, emit)
        with LOCK:
            JOBS[job_id].update(status='done', report=report)
    except Exception as exc:
        # Do not expose request headers, API credentials or provider response bodies.
        with LOCK:
            JOBS[job_id].update(status='error', error=(str(exc)[:300] if isinstance(exc, ValueError)
                                                     else '处理失败：请检查模型配置、网络或视频格式。'))
    finally:
        ACTIVE.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        super().end_headers()

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self, limit=1024*1024):
        length = int(self.headers.get('Content-Length', '0'))
        if length < 0 or length > limit:
            raise ValueError('文件过大；视频上限 60 MB')
        return self.rfile.read(length)

    def serve_file(self, path):
        if not path.is_file():
            return self.send_json({'error': '文件不存在'}, 404)
        size = path.stat().st_size
        start, end, code = 0, size-1, 200
        range_header = self.headers.get('Range')
        if range_header:
            import re
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', range_header)
            if not match:
                return self.send_json({'error': '不支持此 Range'}, 416)
            start = int(match[1])
            end = min(int(match[2]) if match[2] else end, end)
            if start > end:
                return self.send_json({'error': 'Range 越界'}, 416)
            code = 206
        self.send_response(code)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end-start+1))
        if code == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with path.open('rb') as f:
            f.seek(start)
            left = end-start+1
            while left:
                block = f.read(min(left, 65536))
                if not block:
                    break
                self.wfile.write(block)
                left -= len(block)

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path == '/api/health':
                return self.send_json({'status': 'ok', **provider_status(check_connection=True)})
            if path == '/api/videos':
                videos = []
                for folder in video_roots():
                    for p in sorted(folder.glob('*/meta.json')):
                        m = json.loads(p.read_text(encoding='utf-8'))
                        videos.append(m)
                return self.send_json(videos)
            if path.startswith('/api/runs/'):
                job_id = path.split('/')[3]
                if len(job_id) != 32 or not all(c in '0123456789abcdef' for c in job_id):
                    raise ValueError('无效任务 ID')
                with LOCK:
                    job = JOBS.get(job_id)
                    if job:
                        return self.send_json(copy_job(job))
                report_path = DATA/'runs'/job_id/'report.json'
                if report_path.exists():
                    return self.send_json({'id': job_id, 'status': 'done', 'events': [],
                                           'report': enrich_report(json.loads(report_path.read_text(encoding='utf-8')))})
                return self.send_json({'error': '任务不存在'}, 404)
            if path.startswith('/media/'):
                parts = path.strip('/').split('/')
                if len(parts) == 3 and parts[2] in ['video.mp4', 'poster.jpg']:
                    _, video = get_meta(parts[1])
                    return self.serve_file(video.parent/parts[2])
            if path.startswith('/artifacts/'):
                parts = path.strip('/').split('/')
                if len(parts) == 3 and len(parts[1]) == 32 and parts[1].isalnum() and (parts[2] == 'report.json' or
                      (parts[2].startswith('grid-') and parts[2].endswith('.jpg') and parts[2][5:-4].isdigit())):
                    artifact = DATA/'runs'/parts[1]/parts[2]
                    if parts[2] == 'report.json' and artifact.is_file():
                        return self.send_json(enrich_report(json.loads(artifact.read_text(encoding='utf-8'))))
                    return self.serve_file(artifact)
            if path == '/':
                index = ROOT/'web'/'index.html'
                if not index.is_file():
                    return self.send_json({'error': '前端尚未构建，请在 frontend 目录执行 pnpm install 和 pnpm build'}, 503)
                return self.serve_file(index)
            if path.startswith('/assets/'):
                asset_root = (ROOT/'web'/'assets').resolve()
                asset = (ROOT/'web'/unquote(path.lstrip('/'))).resolve()
                if asset.is_relative_to(asset_root) and asset.suffix in ['.js', '.css', '.svg', '.png', '.woff', '.woff2', '.ico']:
                    return self.serve_file(asset)
            return self.send_json({'error': '页面不存在'}, 404)
        except (ValueError, KeyError, TypeError) as exc:
            self.send_json({'error': str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        # Prevent a foreign web page from invoking the local server with the user's API credentials.
        origin = self.headers.get('Origin')
        if origin and origin not in [f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}']:
            return self.send_json({'error': '不允许跨站请求'}, 403)
        if self.headers.get('X-FrameProof') != '1':
            return self.send_json({'error': '缺少本地客户端标识'}, 403)
        try:
            path = urlparse(self.path).path
            if path == '/api/upload':
                body = self.read_body(60*1024*1024)
                if not body:
                    raise ValueError('上传文件为空')
                video_id = uuid.uuid4().hex
                folder = DATA/'uploads'/video_id
                folder.mkdir(parents=True)
                video = folder/'video.mp4'
                video.write_bytes(body)
                try:
                    actual = inspect_video(video)
                    if actual['duration_sec'] > 180:
                        raise ValueError('视频时长超过 180 秒')
                    count = min(6, max(1, int(actual['duration_sec']//2)))
                    meta = {**actual, 'video_id': video_id, 'title': '上传视频 · ' + video_id[:6], 'synthetic': False,
                            'prompt': '', 'segmentation': 'equal_duration_heuristic',
                            'shot_table': [{'shot_id': f'Shot #{i+1}', 't_start': actual['duration_sec']*i/count,
                                            't_end': actual['duration_sec']*(i+1)/count} for i in range(count)]}
                    from qc.media import frame
                    frame(video, .1).save(folder/'poster.jpg')
                    (folder/'meta.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
                    return self.send_json(meta, 201)
                except Exception:
                    # Only remove files created inside this newly generated upload folder.
                    for child in folder.iterdir():
                        if child.is_file():
                            child.unlink()
                    folder.rmdir()
                    raise
            data = json.loads(self.read_body())
            if path == '/api/runs':
                meta, video = get_meta(data.get('video_id'))
                if 'metadata' in data:
                    edited = data['metadata']
                    if not isinstance(edited, dict):
                        raise ValueError('metadata 必须是 JSON 对象')
                    # Dataset identity and synthetic flag are trusted server properties.
                    meta.update({k: edited[k] for k in ['prompt', 'shot_table', 'gen_params'] if k in edited})
                mode = data.get('mode', 'offline')
                budget = data.get('step_budget', 8)
                if mode not in ['offline', 'live'] or type(budget) is not int or not 1 <= budget <= 8:
                    raise ValueError('模式或步数预算无效')
                validate_meta(meta, inspect_video(video))
                if not ACTIVE.acquire(blocking=False):
                    return self.send_json({'error': '已有质检任务运行中，请稍后再试'}, 409)
                job_id = uuid.uuid4().hex
                with LOCK:
                    JOBS[job_id] = {'id': job_id, 'status': 'running', 'events': []}
                threading.Thread(target=work, args=(job_id, meta, video, mode, budget), daemon=True).start()
                return self.send_json({'id': job_id}, 202)
            if path == '/api/feedback':
                job_id, note = data.get('run_id'), data.get('note')
                if not isinstance(job_id, str) or len(job_id) != 32 or not job_id.isalnum() or not (DATA/'runs'/job_id/'report.json').exists():
                    raise ValueError('请先完成一次质检')
                if not isinstance(note, str) or not 1 <= len(note.strip()) <= 1000:
                    raise ValueError('复核意见需要 1–1000 字符')
                with sqlite3.connect(DATA/'feedback.sqlite3') as db:
                    db.execute('CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, run_id TEXT, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
                    db.execute('INSERT INTO feedback(run_id,note) VALUES (?,?)', (job_id, note.strip()))
                return self.send_json({'saved': True}, 201)
            return self.send_json({'error': '接口不存在'}, 404)
        except (ValueError, KeyError, TypeError) as exc:
            self.send_json({'error': str(exc)}, 400)
        except Exception:
            self.send_json({'error': '服务处理失败，请检查视频格式和配置'}, 500)


def copy_job(job):
    result = json.loads(json.dumps(job))
    if isinstance(result.get('report'), dict):
        result['report'] = enrich_report(result['report'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=8765, type=int)
    args = parser.parse_args()
    load_env()
    DATA.mkdir(exist_ok=True)
    print('Preparing synthetic demo videos...', flush=True)
    create_fixtures(DATA/'fixtures')
    print(f'FrameProof ready: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
