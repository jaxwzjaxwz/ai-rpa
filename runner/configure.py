"""Load credentials privately; generate UFO config with environment references only."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE_REPO = ROOT.parent / "UFO"
REPO = BASELINE_REPO if BASELINE_REPO.is_dir() else ROOT.parent / "src" / "ufo"

def model_environment():
    config = json.loads((ROOT / "model.local.json").read_text(encoding="utf-8-sig"))
    key = os.environ.get("UFO_API_KEY") or config.get("api_key", "")
    if not key or key == "PASTE_YOUR_API_KEY_HERE":
        raise ValueError("Fill api_key in ufo_baseline/model.local.json first.")
    env = os.environ.copy()
    model = os.environ.get("UFO_MODEL") or config["model"]
    base = config["api_base"].rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[:-len("/chat/completions")]
    env.update(UFO_API_KEY=key, UFO_API_BASE=base, UFO_MODEL=model,
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return env, {"api_base": base, "model": model}

def write_config():
    # JSON is valid YAML. Secrets are expanded by UFO only in its child process.
    agents = {}
    for name in ("HOST_AGENT", "APP_AGENT", "BACKUP_AGENT", "EVALUATION_AGENT"):
        agents[name] = dict(VISUAL_MODE=True, REASONING_MODEL=False, JSON_SCHEMA=False,
                            FORCE_JSON_OUTPUT=True, DISABLE_MODEL_THINKING=True,
                            RATE_LIMIT_BACKOFF=[10, 20],
                            API_TYPE="openai", API_BASE="${UFO_API_BASE}",
                            API_KEY="${UFO_API_KEY}", API_MODEL="${UFO_MODEL}", API_VERSION="")
    agents["HOST_AGENT"].update(PROMPT="ufo/prompts/share/base/host_agent.yaml",
        EXAMPLE_PROMPT="ufo/prompts/examples/{mode}/host_agent_example.yaml")
    agents["APP_AGENT"].update(PROMPT="ufo/prompts/share/base/app_agent.yaml",
        EXAMPLE_PROMPT="ufo/prompts/examples/{mode}/app_agent_example.yaml",
        EXAMPLE_PROMPT_AS="ufo/prompts/examples/{mode}/app_agent_example_as.yaml")
    (REPO / "config/ufo/agents.yaml").write_text(json.dumps(agents, indent=2), encoding="utf-8")
    overrides = dict(MAX_STEP=25, MAX_ROUND=1, MAX_RETRY=0, TIMEOUT=60, TOP_P=0.8, JSON_PARSING_RETRY=2,
        TEMPERATURE=0.1, SLEEP_TIME=3, SAVE_UI_TREE=True, LOG_XML=True, LOG_TO_MARKDOWN=True,
        SAVE_FULL_SCREEN=False, EVA_SESSION=False, EVA_ROUND=False, USE_MCP=False,
        ENABLED_THIRD_PARTY_AGENTS=[], SAVE_EXPERIENCE="always_not", SAFE_GUARD=True)
    (REPO / "config/ufo/zz_baseline.yaml").write_text(json.dumps(overrides, indent=2), encoding="utf-8")

if __name__ == "__main__":
    write_config()
    try:
        _, public = model_environment()
        print(json.dumps({"configured": True, **public}))
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(2)
