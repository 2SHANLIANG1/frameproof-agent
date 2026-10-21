"""Real decoding and reproducible synthetic assets, with no remote media."""
import io
import json
import math
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _run(args, **kwargs):
    result = subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', *args],
                            capture_output=True, timeout=120, **kwargs)
    if result.returncode:
        raise ValueError('Video decode failed: ' + result.stderr.decode(errors='replace')[-500:])
    return result.stdout


def inspect_video(path):
    result = subprocess.run([FFMPEG, '-hide_banner', '-i', str(path)], capture_output=True, timeout=30)
    info = result.stderr.decode(errors='replace')
    duration = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', info)
    size = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', info)
    if not duration or not size:
        raise ValueError('无法解码视频；请使用 MP4 / MOV / WebM。')
    h, m, s = map(float, duration.groups())
    return {'duration_sec': h * 3600 + m * 60 + s, 'width': int(size[1]),
            'height': int(size[2]), 'audio_track': 'Audio:' in info}


def frame(path, second, width=576):
    raw = _run(['-ss', str(max(0, second)), '-i', str(path), '-frames:v', '1',
                '-vf', f'scale={width}:-1', '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1'])
    if not raw:
        raise ValueError('未读取到有效视频帧')
    return Image.open(io.BytesIO(raw)).convert('RGB')


def audio_rms(path, start, duration):
    import array
    raw = _run(['-ss', str(start), '-t', str(duration), '-i', str(path), '-vn',
                '-ac', '1', '-ar', '8000', '-f', 'f32le', 'pipe:1'])
    values = array.array('f', raw)
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


def uniform_times(start, end, count):
    if end <= start or count <= 0:
        return []
    return [start + (i + .5) * (end - start) / count for i in range(count)]


def sample_times(interval, shots, n_min=24, n_max=144):
    start, end = interval
    if end <= start:
        return []
    cuts = [s['t_start'] for s in shots if start < s['t_start'] < end]
    count = max(n_min, min(n_max, math.ceil((end - start) / 10 + 2 * len(cuts))))
    # Explicitly preserve both sides of cuts, rather than only increasing uniform density.
    boundary = sorted({round(max(start, min(end - .001, t + delta)), 4)
                       for t in cuts for delta in [-.08, .08]})
    if len(boundary) > count:
        boundary = [boundary[int(i * len(boundary) / count)] for i in range(count)]
    times = set(boundary)
    for t in uniform_times(start, end, count - len(times)):
        if len(times) >= count:
            break
        times.add(round(t, 4))
    # Rare collisions with a cut point must not reduce the advertised budget.
    for t in uniform_times(start, end, count * 3):
        if len(times) >= count:
            break
        times.add(round(t, 6))
    return sorted(times)


def contact_sheets(path, times, directory):
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for batch_start in range(0, len(times), 8):
        sheet = Image.new('RGB', (4 * 240, 2 * 160), '#111827')
        draw = ImageDraw.Draw(sheet)
        for k, t in enumerate(times[batch_start:batch_start + 8]):
            img = frame(path, t, 240)
            img.thumbnail((240, 135))
            x, y = k % 4 * 240, k // 4 * 160
            sheet.paste(img, (x, y))
            draw.text((x + 8, y + 138), f'F{batch_start+k+1:03} | {t:.2f}s', fill='white')
        name = f'grid-{batch_start // 8 + 1}.jpg'
        sheet.save(directory / name, quality=85)
        files.append(name)
    return files


def create_fixtures(root):
    """A controlled color patch is a test target, never represented as natural video understanding."""
    root.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for scenario, title in [('drift', '雨夜档案 · 外观漂移'), ('clean', '雨夜档案 · 正常对照'),
                             ('black', '雨夜档案 · 黑帧拦截')]:
        directory = root / scenario
        directory.mkdir(exist_ok=True)
        path = directory / 'video.mp4'
        if not path.exists():
            frames = bytearray()
            for shot in range(6):
                im = Image.new('RGB', (640, 360), '#142735' if shot in [2, 3] else '#25373c')
                d = ImageDraw.Draw(im)
                for x in range(20, 640, 65):
                    d.rectangle((x, 65, x + 45, 270), fill='#344e55', outline='#49666b')
                if shot in [2, 3]:
                    for x in range(0, 640, 23):
                        d.line((x, 0, x - 60, 360), fill='#527183', width=1)
                coat = '#283b56' if scenario == 'drift' and shot == 3 else '#d1b48a'
                d.ellipse((286, 60, 354, 128), fill='#ddb492')
                d.polygon([(280, 132), (360, 132), (397, 290), (243, 290)], fill=coat)
                d.rectangle((285, 208, 350, 250), fill='#9a583e', outline='#d09a63', width=3)
                d.rectangle((0, 308, 640, 360), fill='#101c26')
                d.text((24, 320), f'FRAMEPROOF / SYNTHETIC TEST   |   SHOT {shot+1:02}', fill='#dce8e5')
                d.text((24, 24), ['NEWSROOM', 'ARCHIVE', 'ROOFTOP / RAIN', 'ROOFTOP / RAIN', 'ARCHIVE', 'END'][shot], fill='#dce8e5')
                if scenario == 'black' and shot == 3:
                    im = Image.new('RGB', (640, 360), 'black')
                frames.extend(im.tobytes() * 16)
            _run(['-y', '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '640x360',
                  '-framerate', '8', '-i', 'pipe:0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                  '-movflags', '+faststart', str(path)], input=bytes(frames))
        meta = {'video_id': scenario, 'title': title, 'duration_sec': 12, 'audio_track': False,
                'synthetic': True, 'prompt': '女记者穿米色风衣，在雨夜天台追查旧案，最终回到档案室。',
                'gen_params': {'resolution': [640, 360]},
                'shot_table': [{'shot_id': f'Shot #{i+1}', 't_start': i*2, 't_end': (i+1)*2}
                               for i in range(6)],
                'requirements': [{'text': '雨夜天台', 'shots': ['Shot #3', 'Shot #4']}],
                'expected_defect_shots': ['Shot #4'] if scenario != 'clean' else []}
        (directory / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        poster = directory / 'poster.jpg'
        if not poster.exists():
            frame(path, 6.5).save(poster)
        fixtures.append(meta)
    return fixtures
