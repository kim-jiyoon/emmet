import json
import os
from pprint import pprint

import pytest
from monty.json import MontyDecoder
from monty.serialization import dumpfn, loadfn
from pymatgen import Composition
from pymatgen.apps.battery.conversion_battery import ConversionElectrode
from pymatgen.apps.battery.insertion_battery import InsertionElectrode
from pymatgen.entries.computed_entries import ComputedEntry

from emmet.core.electrode import (
    ConversionElectrodeDoc,
    ConversionVoltagePairDoc,
    InsertionElectrodeDoc,
    InsertionVoltagePairDoc,
)


@pytest.fixture(scope="session")
def insertion_elec(test_dir):
    """
    Recycle the test cases from pymatgen
    """
    entry_Li = ComputedEntry("Li", -1.90753119)
    # more cases can be added later if problems are found
    entries_LTO = loadfn(test_dir / "LiTiO2_batt.json")
    ie_LTO = InsertionElectrode.from_entries(entries_LTO, entry_Li)

    d = {
        "LTO": (ie_LTO, entries_LTO[0].structure, entry_Li),
    }
    return d


kmap = {"specific_energy": "energy_grav", "energy_density": "energy_vol"}


@pytest.fixture(scope="session")
def conversion_elec(test_dir):
    conversion_eletrodes = {}

    entries_LCO = loadfn(test_dir / "LiCoO2_batt.json")
    c = ConversionElectrode.from_composition_and_entries(
        Composition("LiCoO2"), entries_LCO, working_ion_symbol="Li"
    )
    conversion_eletrodes["LiCoO2"] = {
        "working_ion": "Li",
        "CE": c,
        "entries": entries_LCO,
    }

    expected_properties = {
        "LiCoO2": {
            "average_voltage": 2.26940307125,
            "capacity_grav": 903.19752911225669,
            "capacity_vol": 2903.35804724,
            "energy_grav": 2049.7192465127678,
            "energy_vol": 6588.8896693479574,
        }
    }

    return {
        k: (conversion_eletrodes[k], expected_properties[k])
        for k in conversion_eletrodes.keys()
    }


def test_InsertionDocs(insertion_elec):
    for k, (elec, struct, wion_entry) in insertion_elec.items():
        # Make sure that main document can be created using an InsertionElectrode object
        ie = InsertionElectrodeDoc.from_entries(
            grouped_entries=elec._stable_entries,
            working_ion_entry=wion_entry,
            task_id="mp-1234",
            host_structure=struct,
        )
        assert ie.average_voltage == elec.get_average_voltage()
        # Make sure that each adjacent pair can be converted into a sub electrode
        for sub_elec in elec.get_sub_electrodes(adjacent_only=True):
            vp = InsertionVoltagePairDoc.from_sub_electrode(sub_electrode=sub_elec)
            assert vp.average_voltage == sub_elec.get_average_voltage()


def test_ConversionDocs_from_entries(conversion_elec):
    for k, (elec, expected) in conversion_elec.items():
        vp = ConversionElectrodeDoc.from_composition_and_entries(
            Composition(k),
            entries=elec["entries"],
            working_ion_symbol=elec["working_ion"],
            task_id="mp-1234",
        )
        res_d = vp.dict()
        for k, v in expected.items():
            assert res_d[k] == pytest.approx(v, 0.01)


def test_ConversionDocs_from_sub_electrodes(conversion_elec):
    for k, (elec, expected) in conversion_elec.items():
        for sub_elec in elec["CE"].get_sub_electrodes(adjacent_only=True):
            vp = ConversionVoltagePairDoc.from_sub_electrode(sub_electrode=sub_elec)
            assert vp.average_voltage == sub_elec.get_average_voltage()
