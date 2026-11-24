# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "explorer"


def test_language_switch_is_persisted_and_applies_to_dynamic_content():
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "nextbtc-language" in i18n
    assert "MutationObserver" in i18n
    assert "applyTranslations(root)" in app
    assert "setLanguage(getLanguage()==='en'?'zh-CN':'en')" in app
    assert 'id="language-toggle"' in html


def test_bilingual_dictionary_covers_core_explorer_areas():
    i18n = (WEB / "i18n.js").read_text(encoding="utf-8")
    for phrase in [
        "Network Overview", "DWG Analysis", "Mempool History", "Block hash",
        "Transaction hash", "Confirmed balance", "Fee Rate Distribution",
        "Submit a Signed Transaction", "Average block interval", "Target block interval",
    ]:
        assert phrase in i18n


def test_dwg_explains_average_and_target_block_interval_using_core_target_spacing():
    network = (WEB / "network.js").read_text(encoding="utf-8")
    assert "Number(p.actual_timespan)/intervals" in network
    assert "Number(targetSpacing)" in network
    assert "p.timestamp_intervals" in network
    assert "prediction(d.next_block,d.target_spacing_seconds)" in network
    assert "24 个区块头之间有 23 个时间间隔" in network
