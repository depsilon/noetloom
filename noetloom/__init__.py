"""Noetloom source-checkout generation kit. Generated projects need no import of it."""
__version__ = "0.3.0"

# One public catalog for generation and distribution. Bootstrap belongs to the kit;
# the remaining skills operate the generated project without the kit installed.
PROJECT_SKILLS = (
    "noetloom-intake", "noetloom-work", "noetloom-verify",
    "noetloom-grounding", "noetloom-continuity", "noetloom-subagents",
)
FRAMEWORK_SKILLS = ("noetloom-bootstrap", *PROJECT_SKILLS)
