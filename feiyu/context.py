"""Context boundaries for prompt construction and future compression checks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextLayers:
    rules: str
    project: str = ''
    task: str = ''
    evidence: str = ''
    recall: str = ''

    @property
    def stable(self):
        return self.rules + self.project

    @property
    def volatile(self):
        return self.task + self.evidence + self.recall

    def apply(self, backend):
        setter = getattr(backend, 'set_context', None)
        if callable(setter):
            setter(self.stable, self.volatile)
        else:
            backend.set_system(self.stable + self.volatile)
