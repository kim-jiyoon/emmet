""" Core definition of a VASP Task Document """
from typing import Any, ClassVar, Dict, List, Union

from pydantic import BaseModel, Field
from pymatgen.analysis.structure_analyzer import oxide_type
from pymatgen.core import Structure
from pymatgen.entries.computed_entries import ComputedEntry, ComputedStructureEntry

from emmet.core.math import Matrix3D, Vector3D
from emmet.core.structure import StructureMetadata
from emmet.core.task import TaskDocument as BaseTaskDocument
from emmet.core.utils import ValueEnum
from emmet.core.vasp.calc_types import RunType, calc_type, run_type, task_type


class Status(ValueEnum):
    """
    VASP Calculation State
    """

    SUCESS = "successful"
    FAILED = "failed"


class InputSummary(BaseModel):
    """
    Summary of inputs for a VASP calculation
    """

    structure: Structure = Field(None, description="The input structure object")
    parameters: Dict = Field(
        {},
        description="Input parameters from VASPRUN for the last calculation in the series",
    )
    pseudo_potentials: Dict = Field(
        {}, description="Summary of the pseudopotentials used in this calculation"
    )

    potcar_spec: List[Dict] = Field(
        [], description="Potcar specification as a title and hash"
    )

    is_hubbard: bool = Field(False, description="Is this a Hubbard +U calculation.")

    hubbards: Dict = Field({}, description="The hubbard parameters used.")


class OutputSummary(BaseModel):
    """
    Summary of the outputs for a VASP calculation
    """

    structure: Structure = Field(None, description="The output structure object")
    energy: float = Field(
        None, description="The final total DFT energy for the last calculation"
    )
    energy_per_atom: float = Field(
        None, description="The final DFT energy per atom for the last calculation"
    )
    bandgap: float = Field(None, description="The DFT bandgap for the last calculation")
    forces: List[Vector3D] = Field(
        [], description="Forces on atoms from the last calculation"
    )
    stress: Matrix3D = Field(
        [], description="Stress on the unitcell from the last calculation"
    )


class RunStatistics(BaseModel):
    """
    Summary of the Run statistics for a VASP calculation
    """

    average_memory: float = Field(None, description="The average memory used in kb")
    max_memory: float = Field(None, description="The maximum memory used in kb")
    elapsed_time: float = Field(None, description="The real time elapsed in seconds")
    system_time: float = Field(None, description="The system CPU time in seconds")
    user_time: float = Field(
        None, description="The user CPU time spent by VASP in seconds"
    )
    total_time: float = Field(
        None, description="The total CPU time for this calculation"
    )
    cores: Union[int, str] = Field(
        None,
        description="The number of cores used by VASP (some clusters print `mpi-ranks` here)",
    )


class TaskDocument(BaseTaskDocument, StructureMetadata):
    """
    Definition of VASP Task Document
    """

    calc_code: ClassVar[str] = "VASP"
    run_stats: Dict[str, RunStatistics] = Field(
        {},
        description="Summary of runtime statisitics for each calcualtion in this task",
    )

    is_valid: bool = Field(
        True, description="Whether this task document passed validation or not"
    )

    input: InputSummary = Field(InputSummary())
    output: OutputSummary = Field(OutputSummary())

    state: Status = Field(None, description="State of this calculation")

    orig_inputs: Dict[str, Any] = Field(
        {}, description="Summary of the original VASP inputs"
    )

    calcs_reversed: List[Dict] = Field(
        [], description="The 'raw' calculation docs used to assembled this task"
    )

    @property
    def run_type(self) -> RunType:
        params = self.calcs_reversed[0].get("input", {}).get("parameters", {})
        ldau_fields = {
            k: self.calcs_reversed[0].get("input", {}).get("incar", {}).get(k, [])
            for k in ["LDAUL", "LDAUJ", "LDAUU"]
        }
        return run_type({**params, **ldau_fields})

    @property
    def task_type(self):
        return task_type(self.orig_inputs)

    @property
    def calc_type(self):
        params = self.calcs_reversed[0].get("input", {}).get("parameters", {})
        ldau_fields = {
            k: self.calcs_reversed[0].get("input", {}).get("incar", {}).get(k, [])
            for k in ["LDAUL", "LDAUJ", "LDAUU"]
        }
        return calc_type(
            self.orig_inputs,
            {**params, **ldau_fields},
        )

    @property
    def entry(self) -> ComputedEntry:
        """Turns a Task Doc into a ComputedEntry"""
        entry_dict = {
            "correction": 0.0,
            "entry_id": self.task_id,
            "composition": self.output.structure.composition,
            "energy": self.output.energy,
            "parameters": {
                "potcar_spec": self.input.potcar_spec,
                "is_hubbard": self.input.is_hubbard,
                "hubbards": self.input.hubbards,
                # This is done to be compatible with MontyEncoder for the ComputedEntry
                "run_type": str(self.run_type),
            },
            "data": {
                "oxide_type": oxide_type(self.output.structure),
                "aspherical": self.input.parameters.get("LASPH", True),
                "last_updated": self.last_updated,
            },
        }

        return ComputedEntry.from_dict(entry_dict)

    @property
    def structure_entry(self) -> ComputedStructureEntry:
        """Turns a Task Doc into a ComputedStructureEntry"""
        entry_dict = self.entry.as_dict()
        entry_dict["structure"] = self.output.structure

        return ComputedStructureEntry.from_dict(entry_dict)
