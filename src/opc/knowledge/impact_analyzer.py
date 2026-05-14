"""Lightweight code impact analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .import_graph import ImportGraph
from .symbol_search import SymbolIndex
from .test_association import TestFileAssociator


@dataclass
class ImpactResult:
    target_files: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    possible_callers: list[str] = field(default_factory=list)
    related_tests: list[str] = field(default_factory=list)
    risk_points: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)


class ImpactAnalyzer:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir.resolve()

    def analyze(self, changed_files: list[str]) -> ImpactResult:
        graph = ImportGraph()
        graph.index_directory(self.project_dir)
        symbols = SymbolIndex()
        symbols.index_directory(self.project_dir)
        tests = TestFileAssociator(self.project_dir)

        target_files = [self._project_path(file_path) for file_path in changed_files]
        related_files: set[str] = set()
        possible_callers: set[str] = set()
        related_tests: set[str] = set()
        risk_points: list[str] = []

        for target in target_files:
            target_str = str(target)
            dependencies = graph.file_dependencies_of(target_str)
            dependents = graph.file_dependents_of(target_str)
            related_files.update(self._relative(dep) for dep in dependencies)
            related_files.update(self._relative(dep) for dep in dependents)
            possible_callers.update(self._relative(dep) for dep in dependents)
            related_tests.update(self._relative(test) for test in tests.find_tests_for(target_str))

            definitions = symbols.definitions_in_file(target_str)
            if definitions:
                names = ", ".join(symbol.name for symbol in definitions[:5])
                risk_points.append(f"symbols touched in {self._relative(target_str)}: {names}")
            if dependents:
                risk_points.append(f"{self._relative(target_str)} has {len(dependents)} dependent file(s)")
            if not related_tests:
                risk_points.append(f"no related tests found for {self._relative(target_str)}")

        return ImpactResult(
            target_files=[self._relative(path) for path in target_files],
            related_files=sorted(related_files),
            possible_callers=sorted(possible_callers),
            related_tests=sorted(related_tests),
            risk_points=risk_points,
            validation_commands=[f"python -m pytest {test}" for test in sorted(related_tests)],
        )

    def _project_path(self, file_path: str) -> Path:
        path = Path(file_path)
        if path.is_absolute():
            return path
        return self.project_dir / path

    def _relative(self, file_path: str | Path) -> str:
        path = Path(file_path)
        try:
            return path.relative_to(self.project_dir).as_posix()
        except ValueError:
            return path.as_posix()
