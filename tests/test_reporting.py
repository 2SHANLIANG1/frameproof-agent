import pytest
from qc.reporting import build_summary, enrich_report


def test_incomplete_no_findings_never_claims_pass():
    summary=build_summary({'findings':[], 'coverage':[{'status':'incomplete'}]})
    assert summary['headline']=='当前证据不足，需继续检查'
    assert not summary['coverage_complete']
    assert '不能据此认定全片通过' in summary['coverage_text']


def test_confirmed_and_suspected_remain_distinct():
    report={'findings':[
        {'shot_id':'Shot #4','zone':'confirmed','defect_type':'character_appearance_drift','evidence':'蓝色外套','timestamp':6},
        {'shot_id':'Shot #5','zone':'suspected','defect_type':'physical_anomaly','evidence':'疑似畸变'}],
        'coverage':[{'status':'sampled'}]}
    summary=build_summary(report)
    assert (summary['confirmed_count'],summary['suspected_count'])==(1,1)
    assert summary['affected_shots']==['Shot #4','Shot #5']
    assert summary['key_findings'][0]['evidence']=='蓝色外套'
    assert summary['key_findings'][1]['zone']=='suspected'
    assert '疑似' in summary['overview']


def test_rule_abort_reports_unchecked_scope():
    summary=build_summary({'findings':[{'shot_id':'GLOBAL','zone':'confirmed','defect_type':'shot_table_mismatch'}],
                           'coverage':[{'status':'skipped'}]})
    assert not summary['affected_shots']
    assert '全片参数或镜头表' in summary['overview']
    assert '跳过' in summary['coverage_text']


def test_complete_scope_only_and_missing_coverage():
    assert build_summary({'findings':[],'coverage':[{'status':'complete'}]})['coverage_complete']
    assert not build_summary({'findings':[]})['coverage_complete']


def test_archive_enrichment_does_not_mutate_evidence():
    original={'findings':[],'coverage':[{'status':'unsupported'}], 'tokens':123}
    enriched=enrich_report(original)
    assert 'summary' not in original
    assert enriched['tokens']==123
    assert enriched['summary']==enrich_report(enriched)['summary']


def test_sampled_without_findings_is_distinct_from_unfinished_and_pass():
    summary = build_summary({'findings': [], 'coverage': [{'status': 'sampled',
                            'checked_shot_ids': ['a','b'], 'total_shots': 2}]})
    assert summary['headline'] == '抽样检查完成，未检出缺陷'
    assert summary['outcome'] == 'sampled_clear'
    assert summary['tasks_finished']
    assert not summary['coverage_complete']
    assert '逐帧' in summary['coverage_text']
    assert '补齐' not in summary['next_action']
    assert '复核' not in summary['verdict_label']


@pytest.mark.parametrize('coverage', [
    [{'status': 'sampled'}],
    [{'status': 'sampled', 'checked_shot_ids': ['a'], 'total_shots': 2}],
    [{'status': 'sampled', 'checked_shot_ids': ['a','a'], 'total_shots': 2}],
    [{'status': 'sampled', 'checked_shot_ids': ['a'], 'total_shots': 1}, {'status':'unsupported'}],
])
def test_partial_or_unknown_sampling_cannot_look_finished(coverage):
    summary = build_summary({'findings': [], 'coverage': coverage})
    assert summary['outcome'] == 'incomplete'
    assert not summary['tasks_finished']


@pytest.mark.parametrize('zone,outcome', [('suspected','suspected'),('confirmed','defects_found')])
def test_findings_take_priority_over_finished_sampling(zone, outcome):
    summary = build_summary({'findings': [{'shot_id':'a','zone':zone}],
                            'coverage': [{'status':'sampled', 'checked_shot_ids':['a'], 'total_shots':1}]})
    assert summary['outcome'] == outcome
    assert '未检出缺陷' not in summary['verdict_label']
