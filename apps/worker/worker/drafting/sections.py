"""Document skeletons.

A skeleton is a fixed product decision, not something the model chooses: the
outline call annotates the sections below, it never adds, removes or reorders
them. That is what keeps two drafts of the same kind comparable, and what
stops a model dropping an inconvenient section.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    #: Gateway alias — `reasoner` for financial or viability reasoning.
    alias: str = "drafter"
    #: Retrieve and cite vault excerpts for this section.
    uses_vault: bool = False
    #: Name of a data table the module renders after the narrative. The model
    #: is told to refer to it, never to repeat the numbers.
    table: str | None = None
    guidance: str = ""
