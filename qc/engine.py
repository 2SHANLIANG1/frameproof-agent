"""Budgeted evidence harness with a deterministic synthetic controller and optional MLLM."""
import copy
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from PIL import ImageStat
from . import media
from .provider import VisionProvider
from .reporting import build_summary


def validate_meta(meta, actual):
    shots = meta.get('shot_table')
    if not isinstance(shots, list) or not 1 <= len(shots) <= 60:
        raise ValueError('镜头表需要 1–60 个镜头')
    ids, end = set(), 0
    for shot in shots:
        sid = shot.get('shot_id')
        start, stop = shot.get('t_start'), shot.get('t_end')
        if not isinstance(sid, str) or not sid or sid in ids:
            raise ValueError('镜头 ID 必须为不重复的字符串')
        if not all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)
                   for x in [start, stop]):
            raise ValueError('镜头时间必须是有限数字')
        if start < 0 or start < end - .001 or stop <= start or stop > actual['duration_sec'] + 2:
            raise ValueError('镜头区间越界、重叠或长度无效')
        ids.add(sid)
        end = stop
    if actual['duration_sec'] > 180:
        raise ValueError('此 demo 最多处理 180 秒的视频')
    if len(str(meta.get('prompt', ''))) > 4000:
        raise ValueError('提示词最多 4000 字符')


def compile_checklist(meta):
    if not meta.get('prompt') or not meta.get('shot_table'):
        return [{'id': 'general', 'task_type': 'general', 'priority': 0,
                 'question': '检查视频可见缺陷，给出镜头证据'}]
    return [
        {'id': 'consistency', 'task_type': 'consistency', 'priority': 0,
         'question': '主要角色的外观是否跨镜头一致？用前后对照证据定位异常。'},
        {'id': 'adherence', 'task_type': 'adherence', 'priority': 1,
         'question': '逐项核查提示词的场景与动作约束，区分全局约束和场景约束：' + meta['prompt']},
        {'id': 'defect', 'task_type': 'defect', 'priority': 2,
         'question': '检查可见画面缺陷；没有音频转写证据时不要推断音画错位。'}]


@dataclass
class QCMemory:
    focus_cache: dict = field(default_factory=dict)
    entity_cards: dict = field(default_factory=dict)
    ledger: list = field(default_factory=list)
    probe_buffer: dict = field(default_factory=dict)

    def commit(self, action, intent, interval, output):
        self.ledger.append({'step': len(self.ledger) + 1, 'action': action,
                            'intent': intent, 'interval': interval, 'output': copy.deepcopy(output)})
        self.probe_buffer.clear()

    def file_entity(self, shot, value, confidence):
        self.file_attribute('lead', 'coat', shot, value, confidence)

    def file_attribute(self, entity, attribute, shot, value, confidence):
        values = self.entity_cards.setdefault(f'{entity}.{attribute}', [])
        entry = {'shot_id': shot, 'value': value, 'confidence': confidence}
        if entry not in values:
            values.append(entry)

    def snapshot(self, max_chars=6000):
        # Keep latest focus + structured entities, compact old entries; raw pixels never enter text history.
        entity_summary = {key: values[-3:] for key,values in list(self.entity_cards.items())[-12:]}
        result = {'focus': self.focus_cache, 'entities': entity_summary,
                  'recent_evidence': self.ledger[-4:], 'archived_entries': max(0, len(self.ledger) - 4)}
        encoded = json.dumps(result, ensure_ascii=False)
        if len(encoded) > max_chars:
            result['recent_evidence'] = [{k: v for k, v in x.items() if k != 'output'}
                                         for x in self.ledger[-4:]]
            encoded = json.dumps(result, ensure_ascii=False)
        if len(encoded) > max_chars:
            result['entities'] = {key: [{'shot_id':v['shot_id'], 'value':str(v['value'])[:80]}
                                        for v in values[-2:]]
                                  for key, values in list(entity_summary.items())[-6:]}
            result['focus'] = {k:v for k,v in self.focus_cache.items() if k != 'sketch'}
            encoded = json.dumps(result, ensure_ascii=False)
        return encoded[:max_chars]


def rule_prescreen(meta, path, actual):
    findings = []
    for shot in meta['shot_table']:
        start, end = shot['t_start'], min(shot['t_end'], actual['duration_sec'])
        levels = [ImageStat.Stat(media.frame(path, t, 160).convert('L')).mean[0]
                  for t in media.uniform_times(start, end, 4)]
        if levels and all(x < 8 for x in levels):
            findings.append({'shot_id': shot['shot_id'], 'defect_type': 'black_frame',
                             'confidence': 1, 'evidence': f'4 个真实采样点亮度均值均 < 8：{[round(x, 2) for x in levels]}',
                             'zone': 'confirmed', 'source': 'measured_rule'})
        if meta.get('audio_track') and actual['audio_track'] and end - start > 5:
            rms = media.audio_rms(path, start, end-start)
            if rms < .0001:
                findings.append({'shot_id': shot['shot_id'], 'defect_type': 'silent_segment',
                                 'confidence': 1, 'evidence': f'音轨实测 RMS={rms:.7f}，持续 {end-start:.1f}s',
                                 'zone': 'confirmed', 'source': 'measured_rule'})
    if abs(meta['shot_table'][-1]['t_end'] - actual['duration_sec']) > 2:
        findings.append({'shot_id': 'GLOBAL', 'defect_type': 'shot_table_mismatch', 'confidence': 1,
                         'evidence': '镜头表终点与解码时长偏差超过 2 秒', 'zone': 'confirmed', 'source': 'measured_rule'})
    expected = meta.get('gen_params', {}).get('resolution')
    if expected and expected != [actual['width'], actual['height']]:
        findings.append({'shot_id': 'GLOBAL', 'defect_type': 'resolution_anomaly', 'confidence': 1,
                         'evidence': f'实际 {actual["width"]}×{actual["height"]}，声明 {expected}',
                         'zone': 'confirmed', 'source': 'measured_rule'})
    return findings


def patch_color(image):
    # Known synthetic test geometry; explicitly unsupported for arbitrary videos.
    w, h = image.size
    rgb = ImageStat.Stat(image.crop((int(w*.47), int(h*.43), int(w*.53), int(h*.53)))).mean
    return ('米色风衣' if rgb[0] > rgb[2] * 1.2 else '蓝色外套'), [round(v, 1) for v in rgb]


def shot_set_f1(pred, gold):
    pred, gold = set(pred), set(gold)
    if not pred and not gold:
        return 1.0
    return 2 * len(pred & gold) / (len(pred) + len(gold)) if pred or gold else 1.0


def normalize_findings(output, allowed):
    findings = output.get('findings', [])
    if not isinstance(findings, list) or len(findings) > 30:
        raise ValueError('模型 findings 格式无效')
    result = []
    for item in findings:
        confidence = item.get('confidence', 0)
        if item.get('shot_id') not in allowed or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('模型返回了无效镜头或置信度')
        if not isinstance(item.get('evidence'), str) or not isinstance(item.get('defect_type'), str):
            raise ValueError('模型证据字段无效')
        result.append({k: item[k] for k in ['shot_id', 'confidence', 'evidence', 'defect_type']})
    return result


def run_inspection(meta, path, directory, mode='offline', step_budget=8, emit=lambda x: None):
    started = time.perf_counter()
    memory, findings, coverage = QCMemory(), [], []
    provider = VisionProvider() if mode == 'live' else None
    actual = media.inspect_video(path)
    validate_meta(meta, actual)
    queue = compile_checklist(meta)

    def event(kind, title, detail=''):
        emit({'kind': kind, 'title': title, 'detail': detail,
              'elapsed': round(time.perf_counter() - started, 2)})

    event('planner', '编译检查队列', '一致性 → 提示词符合度 → 缺陷；三类检查共用记忆')
    findings = rule_prescreen(meta, path, actual)
    event('rule', '规则预检完成', f'{len(findings)} 项硬缺陷；使用真实解码帧与音轨')
    if not findings:
        times = media.sample_times([0, actual['duration_sec']], meta['shot_table'])
        grids = media.contact_sheets(path, times, directory)
        memory.focus_cache = {'interval': [0, actual['duration_sec']], 'grids': grids, 'num_frames': len(times)}
        memory.commit('shot_selector', '全片粗筛，保留镜头切换前后采样点',
                      [0, actual['duration_sec']], {'grids': grids, 'num_frames': len(times)})
        event('shot_selector', '镜头圈选器已建立焦点', f'{len(times)} 帧 / {len(grids)} 张 4×2 网格')
        if provider:
            from PIL import Image
            event('model', '正在调用模型编译检查项', '本地模型首次加载可能较慢，请等待实际推理结果')
            plan = provider.ask('planner',
                '把生成提示词编译为检查任务。返回 {"entities":["角色或道具"],'
                '"elements":[{"text":"可核查要素","scope":"global"|"scene_bound"}]}。'
                '最多3个实体、4个要素。不要将场景限定词扩展到全片。',
                {'prompt': meta.get('prompt', ''), 'shots': meta['shot_table']})
            entities, elements = plan.get('entities', []), plan.get('elements', [])
            if not isinstance(entities, list) or not isinstance(elements, list):
                raise ValueError('检查项编译器返回格式无效')
            if meta.get('prompt'):
                queue = [{'id':f'entity_{i}', 'task_type':'consistency','priority':0,
                          'question': f'核查实体 {e} 的跨镜头外观一致性', 'entity':e}
                         for i,e in enumerate(entities[:3]) if isinstance(e,str)]
                queue += [{'id':f'element_{i}','task_type':'adherence','priority':1,
                           'question':str(e.get('text',''))[:1000], 'scope':e.get('scope','global')}
                          for i,e in enumerate(elements[:4]) if isinstance(e,dict)]
                queue += [compile_checklist(meta)[-1]]
            event('model', '正在分析真实采帧网格', '视觉模型读取低分辨率全片网格')
            sketch = provider.ask('shot_selector',
                '观察网格并给出区间速写。返回 {"sketch":"角色、场景与可疑镜头的简短速写"}。'
                '每张网格中帧从左到右、从上到下排列，带时间戳；不要把疑似当作结论。',
                {'shots': meta['shot_table'], 'prompt':meta.get('prompt')},
                [('contact sheet', Image.open(directory/g).convert('RGB')) for g in grids[:6]])
            memory.focus_cache['sketch'] = str(sketch.get('sketch', ''))[:1800]
            memory.commit('shot_selector', '对粗筛网格生成区间速写', [0,actual['duration_sec']],
                          {'sketch':memory.focus_cache['sketch']})
            event('planner', '视觉任务队列已编译', f'{len(queue)} 个可核查子问题，已生成区间速写')
            for task in queue:
                done = False
                used = set()
                task_evidence = False
                all_ids = [s['shot_id'] for s in meta['shot_table']]
                def task_coverage(status, reason):
                    return {'task': task['id'], 'status': status, 'exit_reason': reason,
                            'checked_shot_ids': [sid for sid in all_ids if sid in used],
                            'total_shots': len(all_ids),
                            'detail': f'已对 {len(used)}/{len(all_ids)} 个镜头各作两组静帧取证。' +
                            {'all_shots_sampled': '本任务的镜头抽样已完成；静帧抽样不代表逐帧或连续动作检查通过。',
                             'controller_answer': '模型结束本项检查；结论仅适用于已抽样画面。',
                             'answer_without_evidence': '模型未取证即要求结束，尚无判断依据。',
                             'budget_exhausted': '达到本项步数上限，仍有镜头未抽样。'}[reason]}
                for step in range(step_budget):
                    event('model', f'{task["id"]} · 控制决策 {step+1}/{step_budget}', '依据当前记忆选择局部取证镜头')
                    decision = provider.ask('controller',
                        '你是视频质检调度器。基于证据选择下一步。返回 {"action":"probe"|"ANSWER",'
                        '"shot_ids":[镜头ID最多4个],"intent":"简短可公开的行动目的"}。'
                        '未取证不得回答；从 remaining_shot_ids 选取尚未检查的镜头；每次探针会独立抽两组帧复核。',
                        {'task': task, 'shots': meta['shot_table'], 'memory': memory.snapshot(),
                         'checked_shot_ids': [sid for sid in all_ids if sid in used],
                         'remaining_shot_ids': [sid for sid in all_ids if sid not in used],
                         'steps_left': step_budget-step})
                    action = decision.get('action')
                    if action == 'ANSWER':
                        if not task_evidence:
                            coverage.append(task_coverage('incomplete', 'answer_without_evidence'))
                        else:
                            coverage.append(task_coverage('sampled', 'controller_answer'))
                        done = True
                        break
                    ids = decision.get('shot_ids', [])
                    allowed_ids = {s['shot_id'] for s in meta['shot_table']}
                    if action != 'probe' or not isinstance(ids, list) or not 1 <= len(ids) <= 4 or not all(isinstance(s, str) and s in allowed_ids for s in ids):
                        raise ValueError('控制器返回了无效动作或镜头范围')
                    if set(ids) <= used:
                        ids = [sid for sid in all_ids if sid not in used][:4]
                        event('guard', '已纠正重复选镜头', '改为检查尚未取证的镜头：' + ' / '.join(ids))
                    selected = [s for s in meta['shot_table'] if s['shot_id'] in ids]
                    pair_outputs = []
                    observations = []
                    probe_context = copy.deepcopy(memory.entity_cards)
                    for offset in [.35, .65]:
                        event('model', f'{task["id"]} · 视觉探针 {offset}', ' / '.join(ids))
                        images = [(s['shot_id'], media.frame(path, min(actual['duration_sec']-.02,
                                   s['t_start'] + (s['t_end']-s['t_start'])*offset))) for s in selected]
                        memory.probe_buffer['images'] = images
                        out = provider.ask('probe',
                            '分析提供的逐镜头帧，仅报告有证据的缺陷。返回 {"findings":['
                            '{"shot_id":"输入镜头ID","defect_type":"简短类型", "confidence":0到1,'
                            '"evidence":"具体可见证据"}],"entity_verdicts":[{"entity":"实体名",'
                            '"attribute":"属性名","shot_id":"镜头ID","value":"观测值","confidence":0到1}],'
                            '"summary":"简短观察"}。没有证据时 findings 为空。'
                            '帧采样不能证明连续动作、音画同步或全片无缺陷。',
                            {'task': task, 'original_generation_prompt': meta.get('prompt'),
                             'reference_entity_cards': probe_context,
                             'evidence_policy':'仅 original_generation_prompt 是生成目标。档案是待核查观察，不是提示词要求。'
                              '跨镜头差异需比较具体属性，疑似色差不得推断为雨水等原因。仅报告偏离镜头，不将参考镜头报为缺陷。'}, images)
                        pair_outputs.append(normalize_findings(out, set(ids)))
                        observations.append(str(out.get('summary', ''))[:1000])
                        for v in out.get('entity_verdicts', [])[:20]:
                            if not isinstance(v,dict) or v.get('shot_id') not in ids:
                                continue
                            confidence = v.get('confidence',0)
                            if not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not .6 <= confidence <= 1:
                                continue
                            if all(isinstance(v.get(k),str) for k in ['entity','attribute','value']):
                                memory.file_attribute(v['entity'][:80],v['attribute'][:80],v['shot_id'],v['value'][:200],confidence)
                    first, second = pair_outputs
                    for item in first:
                        matches = [x for x in second if (x['shot_id'], x['defect_type']) == (item['shot_id'], item['defect_type'])]
                        confidence = min(item['confidence'], matches[0]['confidence']) if matches else min(.59, item['confidence'])
                        if confidence < .6:
                            event('recheck', '低置信度增强复核', item['shot_id'])
                            extra = provider.ask('recheck', '独立复核此疑似缺陷，返回 {"findings":[{'
                                '"shot_id":"镜头ID","defect_type":"类型","confidence":0到1,"evidence":"可见证据"}]}。',
                                {'candidate': item, 'task': task}, images, enhanced=True)
                            extra_findings = normalize_findings(extra, set(ids))
                            confirmed = [x for x in extra_findings if x['shot_id'] == item['shot_id'] and x['defect_type'] == item['defect_type'] and x['confidence'] >= .6]
                            if matches and confirmed:
                                confidence = min(item['confidence'], matches[0]['confidence'], confirmed[0]['confidence'])
                        item.update(confidence=confidence, zone='confirmed' if confidence >= .6 else 'suspected', source='live_model')
                        findings.append(item)
                    # Second-only detections remain suspected until independent corroboration.
                    for item in second:
                        if not any(x['shot_id'] == item['shot_id'] and x['defect_type'] == item['defect_type'] for x in first):
                            findings.append({**item, 'confidence': min(.59, item['confidence']), 'zone': 'suspected', 'source': 'live_model'})
                    memory.commit('probe', str(decision.get('intent', '逐镜头核查'))[:200],
                                  [selected[0]['t_start'], selected[-1]['t_end']],
                                  {'task': task['id'], 'findings': first, 'verification': second,
                                   'shot_ids': ids, 'observations': observations})
                    used.update(ids)
                    task_evidence = True
                    event('probe', f'{task["id"]} · 取证与独立采样复核', ' / '.join(ids))
                    if used == allowed_ids:
                        coverage.append(task_coverage('sampled', 'all_shots_sampled'))
                        event('coverage', f'{task["id"]} · 镜头抽样已完成', f'{len(used)}/{len(all_ids)} 个镜头；不等于逐帧检查通过')
                        done = True
                        break
                if not done:
                    coverage.append(task_coverage('incomplete', 'budget_exhausted'))
        elif meta.get('synthetic'):
            values = []
            for shot in meta['shot_table']:
                image = media.frame(path, (shot['t_start']+shot['t_end'])/2)
                value, rgb = patch_color(image)
                values.append(value)
                memory.file_entity(shot['shot_id'], value, 1)
                memory.commit('probe', '在已知合成角色区域测量外套色块', [shot['t_start'], shot['t_end']],
                              {'shot_id': shot['shot_id'], 'value': value, 'rgb': rgb})
                event('probe', f'{shot["shot_id"]} · 高分辨率取证', f'{value} · RGB {rgb}')
            baseline = max(set(values), key=values.count)
            for shot, value in zip(meta['shot_table'], values):
                if value != baseline:
                    check, _ = patch_color(media.frame(path, shot['t_start']+.3))
                    confirmed = check == value
                    findings.append({'shot_id': shot['shot_id'], 'defect_type': 'character_appearance_drift',
                        'confidence': 1 if confirmed else .5, 'zone': 'confirmed' if confirmed else 'suspected',
                        'source': 'synthetic_pixel_measurement', 'evidence': f'外套色块为{value}，多数镜头为{baseline}；第二采样点复核{ "一致" if confirmed else "不一致"}。',
                        'evidence_shot_ids': [s['shot_id'] for s, v in zip(meta['shot_table'], values) if v == baseline][:2]})
                    event('verify', '跨镜头属性冲突已复核', shot['shot_id'] + ' 对照多数镜头外观')
            coverage = [{'task': 'consistency', 'status': 'measured', 'detail': '仅验证合成视频已知外套色块，非通用角色识别'},
                        {'task': 'adherence', 'status': 'annotation_only', 'detail': '雨夜天台标签来自样例场景标注，未作模型语义判定'},
                        {'task': 'defect', 'status': 'unsupported', 'detail': '离线模式不识别物理异常；未接入 ASR，不评估音画同步'}]
        else:
            coverage = [{'task': t['id'], 'status': 'unsupported',
                         'detail': '用户视频离线模式只执行规则预检与真实采帧；语义检查需配置真实模型'} for t in queue]
    else:
        times = []
        coverage = [{'task': 'agent', 'status': 'skipped', 'detail': '硬缺陷命中，按设计提前终止；其他维度未检查'}]
    # Deduplicate repeated cross-task findings; prefer independently confirmed evidence.
    unique = {}
    for f in findings:
        key = (f['shot_id'], f['defect_type'])
        if key not in unique or f['confidence'] > unique[key]['confidence']:
            unique[key] = f
    findings = list(unique.values())
    for item in findings:
        shot = next((s for s in meta['shot_table'] if s['shot_id'] == item['shot_id']), None)
        item['timestamp'] = shot['t_start'] if shot else 0
    confirmed = [x for x in findings if x['zone'] == 'confirmed']
    incomplete = any(x['status'] in ['incomplete', 'unsupported', 'skipped', 'annotation_only', 'sampled'] for x in coverage)
    logs = provider.logs if provider else []
    known_usage = all(x['tokens_in'] is not None and x['tokens_out'] is not None for x in logs)
    report = {'schema_version': 1, 'video_id': meta['video_id'], 'title': meta['title'], 'mode': mode,
              'input_prompt': meta.get('prompt',''), 'shot_table':meta['shot_table'],
              'provider': getattr(provider, 'backend', None), 'model': getattr(provider, 'model', None),
              'status': 'fail' if confirmed else 'needs_review' if incomplete or findings else 'pass',
              'elapsed_sec': round(time.perf_counter()-started, 2), 'findings': findings, 'coverage': coverage,
              'queue': queue, 'memory': {'focus_cache': memory.focus_cache, 'entity_cards': memory.entity_cards,
                                        'ledger': memory.ledger, 'probe_buffer': {}},
              'sampled_frames': len(times), 'model_calls': len(logs), 'usage': logs,
              'tokens': sum(x['tokens_in'] + x['tokens_out'] for x in logs) if known_usage else None,
              'limitations': ['合成样例不是生产评测数据', '置信度未经过生产标定', '未接入 ASR；不输出音画错位结论',
                              '语义检查只覆盖已采样镜头，不能保证发现短暂帧级缺陷']}
    report['summary'] = build_summary(report)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    event('report', '逐镜头报告已生成', f'{len(confirmed)} 项确定缺陷 / {len(findings)-len(confirmed)} 项疑似')
    return report
