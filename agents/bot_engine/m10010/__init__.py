"""
m10010 — the data-driven bot script engine, split by responsibility.

Submodules:
  state         shared lazy DB/integration getters, constants, session helpers
  scripts       script loading + step lookup
  steps         step rendering, input processing, skip/action/LLM-route resolution
  done_actions  terminal actions (save message/service-call, escalate, switch script)
  engine        public API: start_session, process_message, get_active_session, reset_session
  seed          default demo script

The public API is re-exported by the parent module ``agents.bot_engine.M10010_bot``.
"""
