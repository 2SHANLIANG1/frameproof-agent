"""Evidence-derived summaries: no extra model call and no invented coverage."""

DEFECT_LABELS = {
    'character_appearance_drift': '角色外观漂移',
    'scene_prop_inconsistency': '场景或道具不一致',
    'physical_anomaly': '画面物理异常',
    'prompt_deviation': '提示词偏离',
    'black_frame': '黑帧', 'silent_segment': '静音片段',
    'resolution_anomaly': '分辨率异常', 'shot_table_mismatch': '镜头表错位',
}


def build_summary(report):
    findings = report.get('findings', [])
    confirmed = [f for f in findings if f.get('zone') == 'confirmed']
    suspected = [f for f in findings if f.get('zone') != 'confirmed']
    shots = list(dict.fromkeys(f['shot_id'] for f in findings if f.get('shot_id') != 'GLOBAL'))
    coverage = report.get('coverage', [])
    counts = {}
    for item in coverage:
        status = item.get('status', 'unknown')
        counts[status] = counts.get(status, 0) + 1
    full = bool(coverage) and all(c.get('status') in ['measured', 'complete'] for c in coverage)
    def finished(item):
        if item.get('status') in ['measured', 'complete']:
            return True
        checked = item.get('checked_shot_ids', [])
        total = item.get('total_shots', 0)
        return (item.get('status') == 'sampled' and isinstance(total, int) and total > 0
                and isinstance(checked, list) and len(set(checked)) == total)
    tasks_finished = bool(coverage) and all(finished(c) for c in coverage)
    outcome = ('defects_found' if confirmed else 'suspected' if suspected else
               'checked_clear' if full else 'sampled_clear' if tasks_finished else 'incomplete')
    if confirmed:
        headline = '发现问题，建议修改后复核'
        overview = f'本次报告包含 {len(confirmed)} 项确定缺陷、{len(suspected)} 项疑似问题。'
    elif suspected:
        headline = '存在疑似问题，需人工复核'
        overview = f'本次未报告确定缺陷，另有 {len(suspected)} 项疑似问题需要人工确认。'
    else:
        if full:
            headline = '已检查项目未发现缺陷'
        elif tasks_finished:
            headline = '抽样检查完成，未检出缺陷'
        else:
            headline = '当前证据不足，需继续检查'
        overview = '本次已执行的检查未报告确定缺陷或疑似问题。'
        if outcome == 'sampled_clear':
            overview = f'本次 {len(coverage)} 项任务均已完成全部镜头的计划抽样，未检出确定缺陷或疑似问题。'
    if shots:
        overview += ' 涉及镜头：' + '、'.join(shots[:8]) + ('等。' if len(shots) > 8 else '。')
    if any(f.get('shot_id') == 'GLOBAL' for f in findings):
        overview += ' 另涉及全片参数或镜头表问题。'
    parts = []
    for status, text in [('measured','项直接检测'), ('complete','项检查完成'),
                         ('sampled','项抽样检查'), ('incomplete','项检查未完成'),
                         ('unsupported','项检查暂不支持'), ('annotation_only','项仅有样例标注'),
                         ('skipped','项检查已跳过')]:
        if counts.get(status):
            parts.append(f'{counts[status]} {text}')
    coverage_text = '；'.join(parts) or '缺少检查覆盖记录'
    if tasks_finished and not full:
        coverage_text += '。计划抽样已完成；结论适用于采样画面，不包含逐帧、连续动作和音画同步检查。'
    elif not full:
        coverage_text += '。不能据此认定全片通过质检。'
    else:
        coverage_text += '。结论仅适用于列出的检查项目。'
    key_findings = [{'shot_id':f.get('shot_id','GLOBAL'),
                     'label':DEFECT_LABELS.get(f.get('defect_type'),f.get('defect_type','未分类问题')),
                     'zone':'confirmed' if f in confirmed else 'suspected',
                     'evidence':f.get('evidence','')[:600], 'timestamp':f.get('timestamp',0)}
                    for f in (confirmed+suspected)[:3]]
    if confirmed:
        next_action = '先核对下方证据，修复对应镜头或参数后重新质检。'
    elif suspected:
        next_action = '人工确认疑似问题，必要时增加取证或重新检查相关镜头。'
    else:
        next_action = '保留本次报告作为已检查项目的记录。'
    if outcome == 'sampled_clear':
        next_action = '本次抽样未发现需要处理的问题，可下载报告。如需检查短暂闪烁或动作连贯性，可另作连续画面检查。'
    elif not tasks_finished:
        next_action += ' 补齐未完成或暂不支持的检查后再作最终判断。'
    labels = {'defects_found':'发现确定缺陷', 'suspected':'存在疑似问题，建议复核',
              'checked_clear':'已检查项目未检出缺陷', 'sampled_clear':'抽样检查完成 · 未检出缺陷',
              'incomplete':'检查不充分 · 请查看覆盖详情'}
    return {'version':2, 'headline':headline, 'overview':overview,
            'outcome':outcome, 'tasks_finished':tasks_finished, 'verdict_label':labels[outcome],
            'confirmed_count':len(confirmed), 'suspected_count':len(suspected),
            'affected_shots':shots, 'coverage_complete':full, 'coverage_text':coverage_text,
            'key_findings':key_findings, 'next_action':next_action,
            'note':'总结依据报告中的证据记录整理；模型结论仍可能误判，置信度不等于准确率。'}


def enrich_report(report):
    return {**report, 'summary':build_summary(report)}
