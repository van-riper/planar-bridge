"""Run-level options that toggle one pull, independent of file config.

These are the runtime switches a caller sets per invocation (today the CLI),
kept separate from the file-backed ``AppConfig``. The type lives at the
package root so both the CLI and the pipeline can depend on it without the
pipeline reaching outward into ``cli/``.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class RunOptions:
    """Per-run switches resolved from the command line.

    Attributes:
        assume_yes (bool): Skip the version-mismatch prompt and proceed.
        dry_run (bool): Run the full decision logic but write nothing to disk.
        only_sets (frozenset[str]): Restrict the run to these set codes; an
            empty set means every set is eligible.
        language (str | None): Override the configured card-language code, or
            None to keep the configured value.
    """

    assume_yes: bool = False
    dry_run: bool = False
    only_sets: frozenset[str] = field(default_factory=frozenset)
    language: str | None = None
