"""
DEPRECATED — DO NOT USE
This file is orphaned dead code from the original Nyay Vani prototype.
All prompt building is now done inside each agent file:
  - Intake prompts: app/agents/intake_agent.py → build_intake_system()
  - Expert prompts: app/agents/legal_agent.py → _build_system()
  - Medical prompts: app/agents/medical_agent.py
  - Scheme prompts: app/agents/scheme_agent.py

This file is kept only to avoid import errors if any old code references it.
Safe to delete entirely once confirmed nothing imports it.
"""

# Legacy stub — raises clear error if accidentally called
def build_intake_prompt(*args, **kwargs):
    raise NotImplementedError(
        "prompt_builder.py is deprecated. Use intake_agent.py → run_intake() instead."
    )

def build_expert_prompt(*args, **kwargs):
    raise NotImplementedError(
        "prompt_builder.py is deprecated. Use legal_agent.py → run_legal_expert_stream() instead."
    )
