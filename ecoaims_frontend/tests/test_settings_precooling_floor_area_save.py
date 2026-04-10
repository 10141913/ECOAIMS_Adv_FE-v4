from ecoaims_frontend.callbacks.precooling_settings_callbacks import _cfg_from_form, _form_from_cfg


def test_settings_precooling_cfg_roundtrip_keeps_floor_area_m2():
    cfg0 = {"building_parameters": {"floor_area_m2": 2222.5}}
    form = _form_from_cfg(cfg0)
    cfg1 = _cfg_from_form(*form)
    assert cfg1["building_parameters"]["floor_area_m2"] == 2222.5
