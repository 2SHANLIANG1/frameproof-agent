import json
from pathlib import Path

import pytest

from qc.engine import (QCMemory, compile_checklist, normalize_findings,
                       run_inspection, shot_set_f1, validate_meta)
from qc.media import create_fixtures, sample_times, inspect_video


@pytest.fixture(scope='session')
def fixtures(tmp_path_factory):
    root = tmp_path_factory.mktemp('videos')
    create_fixtures(root)
    return root


@pytest.mark.parametrize('scenario,expected', [('drift',['Shot #4']),('clean',[]),('black',['Shot #4'])])
def test_real_decoding_pipeline(fixtures, tmp_path, scenario, expected):
    folder = fixtures/scenario
    meta = json.loads((folder/'meta.json').read_text(encoding='utf-8'))
    events = []
    report = run_inspection(meta, folder/'video.mp4', tmp_path/scenario, emit=events.append)
    pred = [f['shot_id'] for f in report['findings'] if f['zone'] == 'confirmed']
    assert pred == expected
    assert shot_set_f1(pred, expected) == 1
    assert report['tokens'] == 0 and report['model_calls'] == 0
    assert report['memory']['probe_buffer'] == {}
    assert json.loads((tmp_path/scenario/'report.json').read_text(encoding='utf-8')) == report
    if scenario == 'black':
        assert report['sampled_frames'] == 0
        assert not any(e['kind'] == 'probe' for e in events)
    else:
        assert report['sampled_frames'] == 24
        assert len(report['memory']['focus_cache']['grids']) == 3
        # A clean synthetic color check cannot declare all semantic tasks passed.
        if scenario == 'clean':
            assert report['status'] == 'needs_review'


def test_upload_offline_never_fakes_semantic_checks(fixtures, tmp_path):
    folder = fixtures/'drift'
    meta = json.loads((folder/'meta.json').read_text(encoding='utf-8'))
    meta['synthetic'] = False
    report = run_inspection(meta, folder/'video.mp4', tmp_path)
    assert not report['findings']
    assert report['status'] == 'needs_review'
    assert all(c['status'] == 'unsupported' for c in report['coverage'])


@pytest.mark.parametrize('pred,gold,expected', [([],[],1),([],['a'],0),(['a'],[],0),
    (['a','b'],['a'],2/3),(['a','a'],['a'],1)])
def test_set_f1(pred, gold, expected):
    assert shot_set_f1(pred,gold) == expected


def test_sampling_spans_interval_and_preserves_cuts():
    shots = [{'t_start': i*2} for i in range(6)]
    times = sample_times([0,12],shots)
    assert len(times) == 24
    assert max(times) > 11 and min(times) < 1
    assert 5.92 in times and 6.08 in times
    assert sample_times([2,2],shots) == []
    assert len(sample_times([0,100000],shots)) == 144


def test_memory_prunes_context_keeps_ledger():
    memory = QCMemory()
    for i in range(25):
        memory.probe_buffer['raw_image'] = b'raw'
        memory.commit('probe',f'check {i}',[i,i+1],{'answer':'x'*1000})
    assert not memory.probe_buffer
    assert len(memory.ledger) == 25
    assert len(memory.snapshot(2000)) <= 2000
    assert 'check 24' in memory.snapshot()


@pytest.mark.parametrize('shots', [[], [{'shot_id':'a','t_start':2,'t_end':1}],
    [{'shot_id':'a','t_start':0,'t_end':2},{'shot_id':'a','t_start':2,'t_end':3}],
    [{'shot_id':'a','t_start':float('nan'),'t_end':2}],
    [{'shot_id':'a','t_start':0,'t_end':3},{'shot_id':'b','t_start':2,'t_end':4}]])
def test_bad_shot_metadata_rejected(shots):
    with pytest.raises(ValueError):
        validate_meta({'shot_table':shots},{'duration_sec':12})


def test_model_output_cannot_invent_shots():
    with pytest.raises(ValueError):
        normalize_findings({'findings':[{'shot_id':'fake','confidence':.9}]},{'Shot #1'})


def test_fallback_queue():
    assert compile_checklist({'prompt':'','shot_table':[]})[0]['id'] == 'general'


def test_budget_harness_with_fake_provider(monkeypatch, fixtures, tmp_path):
    """Contract test, not a claim that a remote provider was exercised."""
    class FakeProvider:
        def __init__(self): self.logs=[]
        def ask(self, role, *args, **kwargs):
            self.logs.append({'role':role,'tokens_in':10,'tokens_out':5})
            if role == 'planner': return {'entities':['lead'], 'elements':[{'text':'rooftop','scope':'scene_bound'}]}
            if role == 'shot_selector': return {'sketch':'controlled test'}
            if role == 'controller': return {'action':'probe','shot_ids':['Shot #1'],'intent':'test'}
            return {'findings':[]}
    monkeypatch.setattr('qc.engine.VisionProvider',FakeProvider)
    folder=fixtures/'clean'
    meta=json.loads((folder/'meta.json').read_text(encoding='utf-8'))
    report=run_inspection(meta,folder/'video.mp4',tmp_path,mode='live',step_budget=1)
    assert len(report['coverage']) == 3
    assert all(x['status']=='incomplete' for x in report['coverage'])
    assert report['tokens'] == report['model_calls']*15
    assert report['status']=='needs_review'


@pytest.mark.parametrize('selections,budget,expected_status,expected_reason,checked', [
    ([[1,2,3,4],[5,6]], 2, 'sampled', 'all_shots_sampled', 6),
    ([[1,2,3,4],[1,2,3,4]], 2, 'sampled', 'all_shots_sampled', 6),
    ([[1]], 1, 'incomplete', 'budget_exhausted', 1),
    ([[]], 1, 'incomplete', 'answer_without_evidence', 0),
])
def test_live_coverage_uses_evidence_not_extra_answer(monkeypatch, tmp_path,
        selections, budget, expected_status, expected_reason, checked):
    """Exercise the real scheduling loop with controlled vision responses."""
    from PIL import Image
    controller_inputs = []
    class Provider:
        def __init__(self):
            self.logs = []
            self.index = 0
        def ask(self, role, instruction, context, *args, **kwargs):
            if role == 'planner': return {'entities': [], 'elements': []}
            if role == 'shot_selector': return {'sketch': 'test'}
            if role == 'controller':
                controller_inputs.append(context)
                ids = selections[self.index]
                self.index += 1
                return {'action': 'probe' if ids else 'ANSWER',
                        'shot_ids': [f'Shot #{i}' for i in ids], 'intent': 'test'}
            return {'findings': [], 'summary': 'No visible defect in sampled frames.'}
    monkeypatch.setattr('qc.engine.VisionProvider', Provider)
    monkeypatch.setattr('qc.engine.rule_prescreen', lambda *args: [])
    monkeypatch.setattr('qc.engine.media.inspect_video', lambda *args: {'duration_sec': 6})
    monkeypatch.setattr('qc.engine.media.sample_times', lambda *args: [])
    monkeypatch.setattr('qc.engine.media.contact_sheets', lambda *args: [])
    monkeypatch.setattr('qc.engine.media.frame', lambda *args: Image.new('RGB', (10,10)))
    meta = {'video_id': 'test', 'title': 'test', 'prompt': 'test',
            'shot_table': [{'shot_id': f'Shot #{i+1}', 't_start': i, 't_end': i+1}
                           for i in range(6)]}
    events = []
    report = run_inspection(meta, tmp_path/'unused.mp4', tmp_path,
                            mode='live', step_budget=budget, emit=events.append)
    coverage = report['coverage'][0]
    assert coverage['status'] == expected_status
    assert coverage['exit_reason'] == expected_reason
    assert len(coverage['checked_shot_ids']) == checked
    assert coverage['total_shots'] == 6
    assert report['status'] == 'needs_review'
    assert not report['summary']['coverage_complete']
    assert controller_inputs[0]['checked_shot_ids'] == []
    if checked:
        probes = [entry['output'] for entry in report['memory']['ledger'] if entry['action'] == 'probe']
        assert probes[0]['observations'] == ['No visible defect in sampled frames.'] * 2
    if len(selections) == 2:
        assert controller_inputs[1]['remaining_shot_ids'] == ['Shot #5', 'Shot #6']
        assert len([e for e in events if e['kind'] == 'probe']) == 2
