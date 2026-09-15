"""示波器面板 -> SCPI 命令映射的测试（不依赖 Qt）。"""
import pytest

from autotest.core import scope_commands as sc


def test_channel_commands():
    assert sc.channel_display(1, True) == ":CHANnel1:DISPlay ON"
    assert sc.channel_display(2, False) == ":CHANnel2:DISPlay OFF"
    assert sc.channel_scale(1, 0.1) == ":CHANnel1:SCALe 0.1"
    assert sc.channel_offset(1, -0.25) == ":CHANnel1:OFFSet -0.25"
    assert sc.channel_coupling(3, "ac") == ":CHANnel3:COUPling AC"
    assert sc.channel_probe(1, 10) == ":CHANnel1:PROBe 10"
    assert sc.channel_bwlimit(1, True) == ":CHANnel1:BWLimit 20M"
    assert sc.channel_bwlimit(1, False) == ":CHANnel1:BWLimit OFF"
    assert sc.channel_invert(1, True) == ":CHANnel1:INVert ON"


def test_timebase_commands():
    assert sc.timebase_scale(200e-6) == ":TIMebase:MAIN:SCALe 0.0002"
    assert sc.timebase_offset(0.0) == ":TIMebase:MAIN:OFFSet 0"


def test_trigger_commands():
    assert sc.trigger_sweep("AUTO") == ":TRIGger:SWEep AUTO"
    assert sc.trigger_sweep("normal") == ":TRIGger:SWEep NORMal"
    assert sc.trigger_source(2) == ":TRIGger:EDGE:SOURce CHANnel2"
    assert sc.trigger_slope("POS") == ":TRIGger:EDGE:SLOPe POSitive"
    assert sc.trigger_level(0.5) == ":TRIGger:EDGE:LEVel 0.5"


def test_acquire_commands():
    assert sc.run() == ":RUN"
    assert sc.stop() == ":STOP"
    assert sc.single() == ":SINGle"
    assert sc.force_trigger() == ":TFORce"
    assert sc.autoset() == ":AUToset"
    assert sc.clear() == ":CLEar"


def test_measure_commands():
    assert sc.measure_item("vpp", 1) == ":MEASure:ITEM VPP,CHANnel1"
    assert sc.measure_item("freq", 2) == ":MEASure:ITEM FREQuency,CHANnel2"
    assert sc.measure_item("RTIMe", 3) == ":MEASure:ITEM RTIMe,CHANnel3"
    assert sc.measure_item_query("vpp", 2) == ":MEASure:ITEM? VPP,CHANnel2"
    assert sc.measure_item_query("freq", 1) == ":MEASure:ITEM? FREQuency,CHANnel1"
    assert sc.measure_clear() == ":MEASure:CLEar"
    assert sc.measure_stat_display(True) == ":MEASure:STATistic:DISPlay ON"
    assert sc.measure_stat_reset() == ":MEASure:STATistic:RESet"


def test_afg_commands():
    assert sc.afg_function("sine") == ":SOURce:FUNCtion SINusoid"
    assert sc.afg_frequency(1000) == ":SOURce:FREQuency 1000"
    assert sc.afg_amplitude(1.0) == ":SOURce:VOLTage:AMPLitude 1"
    assert sc.afg_output(False) == ":SOURce:OUTPut:STATe OFF"
    assert sc.afg_output(True) == ":SOURce:OUTPut:STATe ON"


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        sc.channel_source(5)
    with pytest.raises(ValueError):
        sc.channel_scale(1, 0)
    with pytest.raises(ValueError):
        sc.channel_coupling(1, "XY")
    with pytest.raises(ValueError):
        sc.trigger_slope("up")
    with pytest.raises(ValueError):
        sc.afg_function("triangle")


