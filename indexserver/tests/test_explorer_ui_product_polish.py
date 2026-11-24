# Copyright (c) 2026 btcdage / nextbtc2025
# Project: nextBTC Index Server
# Source: https://github.com/nextbtc2025/indexserver
# License: MIT (see LICENSE)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "explorer"


def test_broadcast_ui_does_not_expose_internal_or_public_wallet_endpoint():
    source = (WEB / "broadcast.js").read_text(encoding="utf-8")
    assert "Wallet API ' + endpoint.href" not in source
    assert "等待交易数据" not in source
    assert "请粘贴已签名的原始交易数据" in source
    assert "交易数据格式有效" in source
    # The configured endpoint remains the actual fetch target; only its display is removed.
    assert "fetch(endpoint" in source


def test_home_mempool_has_automatic_empty_nonempty_collapse_behavior():
    network = (WEB / "network.js").read_text(encoding="utf-8")
    mempool = (WEB / "mempool.js").read_text(encoding="utf-8")
    assert "homeMempoolHasTransactions" in network
    assert "homeMempoolManualExpanded??hasTransactions" in network
    assert "home-pool-content" in network
    assert "home-pool-toggle" in network
    assert "if(sample?.stale)" in network
    assert "onSample?.(sample)" in mempool
    assert "onSample?.({available:false,error})" in mempool


def test_home_mempool_content_is_semantically_hidden_when_collapsed():
    network = (WEB / "network.js").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert 'id="home-pool-content" hidden' in network
    assert ".home-mempool #home-pool-content[hidden]{display:none}" in css
