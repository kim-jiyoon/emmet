from datetime import datetime
from typing import Dict, List, Union

import numpy as np
from pydantic import BaseModel, Field, PyObject
from pymatgen.core import Structure

from emmet.builders import EmmetBuildSettings
from emmet.core import SETTINGS
from emmet.core.mpid import MPID
from emmet.core.utils import DocEnum
from emmet.core.vasp.task import TaskDocument


class DeprecationMessage(DocEnum):
    MANUAL = "M", "manual deprecation"
    KPTS = "C001", "Too few KPoints"
    ENCUT = "C002", "ENCUT too low"
    FORCES = "C003", "Forces too large"
    CONVERGENCE = "E001", "Calculation did not converge"
    MAX_SCF = "E002", "Max SCF gradient too large"
    LDAU = "I001", "LDAU Parameters don't match the inputset"


class ValidationDoc(BaseModel):
    """
    Validation document for a VASP calculation
    """

    task_id: Union[MPID, int] = Field(
        ..., description="The task_id for this validation document"
    )
    valid: bool = Field(False, description="Whether this task is valid or not")
    last_updated: datetime = Field(
        description="Last updated date for this document",
        default_factory=datetime.utcnow,
    )
    reasons: List[Union[DeprecationMessage, str]] = Field(
        None, description="List of deprecation tags detailing why this task isn't valid"
    )
    warnings: List[str] = Field(
        [], description="List of potential warnings about this calculation"
    )
    data: Dict = Field(
        description="Dictioary of data used to perform validation."
        " Useful for post-mortem analysis"
    )

    class Config:
        extra = "allow"

    @classmethod
    def from_task_doc(
        cls,
        task_doc: TaskDocument,
        kpts_tolerance: float = SETTINGS.VASP_KPTS_TOLERANCE,
        input_sets: Dict[str, PyObject] = SETTINGS.VASP_DEFAULT_INPUT_SETS,
        LDAU_fields: List[str] = SETTINGS.VASP_CHECKED_LDAU_FIELDS,
        max_allowed_scf_gradient: float = SETTINGS.VASP_MAX_SCF_GRADIENT,
        deprecated_tags: List["str"] = None,
    ) -> "ValidationDoc":
        """
        Determines if a calculation is valid based on expected input parameters from a pymatgen inputset

        Args:
            task_doc: the task document to process
            input_sets (dict): a dictionary of task_types -> pymatgen input set for validation
            kpts_tolerance (float): the tolerance to allow kpts to lag behind the input set settings
            LDAU_fields (list(String)): LDAU fields to check for consistency
        """

        structure = task_doc.output.structure
        task_type = task_doc.task_type
        inputs = task_doc.orig_inputs

        reasons = []
        data = {}
        dep_tags_ = [] if deprecated_tags is None else deprecated_tags

        if task_type in input_sets:
            valid_input_set = input_sets[task_type](structure)

            # Checking K-Points
            valid_num_kpts = valid_input_set.kpoints.num_kpts or np.prod(
                valid_input_set.kpoints.kpts[0]
            )
            num_kpts = inputs.get("kpoints", {}).get("nkpoints", 0) or np.prod(
                inputs.get("kpoints", {}).get("kpoints", [1, 1, 1])
            )
            data["kpts_ratio"] = num_kpts / valid_num_kpts
            if data["kpts_ratio"] < kpts_tolerance:
                reasons.append(DeprecationMessage.KPTS)

            # Checking ENCUT
            encut = inputs.get("incar", {}).get("ENCUT")
            valid_encut = valid_input_set.incar["ENCUT"]
            data["encut_ratio"] = float(encut) / valid_encut  # type: ignore
            if data["encut_ratio"] < 1:
                reasons.append(DeprecationMessage.ENCUT)

            # Checking U-values
            if valid_input_set.incar.get("LDAU"):
                # Assemble actual input LDAU params into dictionary to account for possibility
                # of differing order of elements
                structure_set_symbol_set = structure.symbol_set
                inputs_ldau_fields = [structure_set_symbol_set] + [
                    inputs.get("incar", {}).get(k, []) for k in LDAU_fields
                ]
                input_ldau_params = {d[0]: d[1:] for d in zip(*inputs_ldau_fields)}

                # Assemble required input_set LDAU params into dictionary
                input_set_symbol_set = valid_input_set.poscar.structure.symbol_set
                input_set_ldau_fields = [input_set_symbol_set] + [
                    valid_input_set.incar.get(k) for k in LDAU_fields
                ]
                input_set_ldau_params = {
                    d[0]: d[1:] for d in zip(*input_set_ldau_fields)
                }

                if any(
                    input_set_ldau_params[el] != input_params
                    for el, input_params in input_ldau_params.items()
                ):
                    reasons.append(DeprecationMessage.LDAU)

            # Check the max upwards SCF step
            skip = inputs.get("incar", {}).get("NLEMDL")
            energies = [
                d["e_fr_energy"]
                for d in task_doc.calcs_reversed[0]["output"]["ionic_steps"][-1][
                    "electronic_steps"
                ]
            ]
            max_gradient = np.max(np.gradient(energies)[skip:])
            data["max_gradient"] = max_gradient
            if max_gradient > max_allowed_scf_gradient:
                reasons.append(DeprecationMessage.MAX_SCF)

        if set(task_doc.tags) | set(dep_tags_):
            reasons.append(DeprecationMessage.MANUAL)

        doc = ValidationDoc(
            task_id=task_doc.task_id,
            task_type=task_doc.task_type,
            run_type=task_doc.run_type,
            valid=len(reasons) == 0,
            reasons=reasons,
            data=data,
        )
        return doc
