"""Module-agnostic document drafting.

`worker/drafts/` was the Groundwork implementation of this pipeline; the
reusable two-thirds now live here so a second vertical does not rebuild
them. The split: this package owns the pipeline, the cost guard, citation
resolution, DOCX assembly and the grounding contract; a module owns its
context pack, its skeletons, its data tables and its registry.
"""
