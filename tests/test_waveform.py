"""真机波形读取相关纯函数测试（无需硬件/Qt）。"""
import struct

import pytest

from autotest.hal.rigol_dho import convert_waveform, parse_preamble
from autotest.hal.scpi import parse_ieee_block


def test_parse_ieee_block_single_digit_length():
    payload, rest = parse_ieee_block(b"#15abcde\n")
    assert payload == b"abcde"
    assert rest == b"\n"


def test_parse_ieee_block_two_digit_length():
    body = bytes(range(10))
    payload, rest = parse_ieee_block(b"#2" + b"10" + body + b"\n")
    assert payload == body
    assert rest == b"\n"


def test_parse_ieee_block_invalid():
    assert parse_ieee_block(b"") == (None, b"")
    assert parse_ieee_block(b"not a block") == (None, b"not a block")
    assert parse_ieee_block(b"#0") == (None, b"#0")
    assert parse_ieee_block(b"#15abc") == (None, b"#15abc")  # 长度不足


def test_parse_preamble():
    text = "0,0,1000,1,1.0E-06,-5.0E-04,0.0,4.0E-03,0.0,128"
    pre = parse_preamble(text)
    assert pre["format"] == 0.0
    assert pre["points"] == 1000.0
    assert pre["xincrement"] == pytest.approx(1e-6)
    assert pre["yincrement"] == pytest.approx(4e-3)
    assert pre["yreference"] == 128.0


def test_parse_preamble_too_short():
    with pytest.raises(ValueError):
        parse_preamble("0,0,1000")


def test_convert_waveform_byte():
    pre = {"format": 0, "yincrement": 0.01, "yorigin": 0.0, "yreference": 128.0}
    volts = convert_waveform(bytes([128, 138, 118]), pre)
    assert volts[0] == pytest.approx(0.0)
    assert volts[1] == pytest.approx(0.1)
    assert volts[2] == pytest.approx(-0.1)


def test_convert_waveform_word():
    pre = {"format": 1, "yincrement": 0.001, "yorigin": 0.0, "yreference": 0.0}
    payload = struct.pack("<3h", 0, 1000, -1000)
    volts = convert_waveform(payload, pre)
    assert len(volts) == 3
    assert volts[0] == pytest.approx(0.0)
    assert volts[1] == pytest.approx(1.0)
    assert volts[2] == pytest.approx(-1.0)
