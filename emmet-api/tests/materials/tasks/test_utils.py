import os
from json import load

from emmet.api.core.settings import MAPISettings
from emmet.api.routes.materials.tasks.utils import calcs_reversed_to_trajectory, task_to_entry


def test_calcs_reversed_to_trajectory():
    with open(
        os.path.join(MAPISettings().TEST_FILES, "calcs_reversed_mp_1031016.json")
    ) as file:
        calcs_reversed = load(file)
        trajectories = calcs_reversed_to_trajectory(calcs_reversed)

    assert len(trajectories) == 1
    assert trajectories[0]["lattice"] == [
        [9.054455, 0.0, 0.0],
        [0.0, 4.500098, 0.0],
        [0.0, 0.0, 4.500098],
    ]


def test_task_to_entry():
    with open(os.path.join(MAPISettings().TEST_FILES, "test_task.json")) as file:
        doc = load(file)

    entry_dict = task_to_entry(doc)
    assert entry_dict["@class"] == "ComputedStructureEntry"
