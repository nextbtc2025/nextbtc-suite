from pathlib import Path


def test_statistics_panels_use_body_slot_not_subtitle_slot():
    source = (Path(__file__).parents[1] / 'web' / 'explorer' / 'statistics.js').read_text(encoding='utf-8')
    assert "t('按当前非零余额地址统计各余额区间'),'<div id=\"distribution\">'" in source
    assert "t('根据 nextBTC 区块补贴及减半规则计算'),'<div id=\"issuance\">'" in source
    assert "root.querySelector('#distribution').innerHTML" in source
    assert "root.querySelector('#issuance').innerHTML" in source


def test_statistics_page_has_all_required_mount_points():
    source = (Path(__file__).parents[1] / 'web' / 'explorer' / 'statistics.js').read_text(encoding='utf-8')
    for selector in ('id=\"supply\"', 'id=\"distribution\"', 'id=\"issuance\"', 'id=\"stats-source\"'):
        assert selector in source
