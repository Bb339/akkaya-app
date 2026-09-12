from dataclasses import asdict
from kds.data.repositories import Document, ProjectRepository
from kds.domain.project import Project
from kds.domain.water_budget import WaterBudget


def project_document(project: Project, water_budget: WaterBudget | None = None) -> Document:
    budget = water_budget or WaterBudget(project.id, project.annual_water_budget, project.water_budget_unit)
    return {"schema_version": 1, "data_revision": 0, "project": asdict(project),
            "analysis_units": [], "crops": [], "economics": [], "water_budget": asdict(budget),
            "imports": {}, "metadata": {}}


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
