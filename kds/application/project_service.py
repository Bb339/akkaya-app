from dataclasses import asdict
from kds.data.repositories import Document, ProjectRepository
from kds.domain.project import Project
from kds.domain.water_budget import WaterBudget


SYNTHETIC_INSTITUTIONAL_DEMO_SOURCE = "synthetic not_official institutional integration fixture"
SYNTHETIC_GENERAL_PROJECT_CLASSIFICATION = "synthetic_test_fixture"


def is_explicit_synthetic_demo(project: Project) -> bool:
    """Recognize only explicit synthetic-demo classifications exposed by the product."""
    classification = project.data_source_notes.strip().casefold()
    return classification in {
        SYNTHETIC_INSTITUTIONAL_DEMO_SOURCE,
        SYNTHETIC_GENERAL_PROJECT_CLASSIFICATION,
    }


def project_document(project: Project, water_budget: WaterBudget | None = None) -> Document:
    budget = water_budget or WaterBudget(project.id, project.annual_water_budget, project.water_budget_unit)
    synthetic_institutional = is_explicit_synthetic_demo(project)
    return {"schema_version": 1, "data_revision": 0, "project": asdict(project),
            "analysis_units": [], "crops": [], "economics": [], "water_budget": asdict(budget),
            "imports": {}, "water_data": {"datasets": {}, "active": {}},
            "economic_data": {"datasets": {}, "active": {}, "dependencies": {}, "reanalysis": {}},
            "crop_parameter_data": {"datasets": {}, "active": {}, "reanalysis": {},
                                    "identity_resolution_revision": "phase7-reviewed-relations-v1"},
            "analysis_state": {"requires_reanalysis": False}, "runs": {},
            "metadata": ({"synthetic_institutional_test": True, "not_official": True,
                          "display_labels": ["SYNTHETIC", "NOT_OFFICIAL"]}
                         if synthetic_institutional else {})}


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create(self, values: Document) -> Document:
        project = Project(**values)
        return self.repository.create(project_document(project))["project"]

    def list(self) -> list[Document]:
        return self.repository.list_projects()

    def get(self, project_id: str) -> Document:
        return self.repository.get(project_id)
