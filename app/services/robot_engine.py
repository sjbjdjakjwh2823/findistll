import os
import sys
from app.services.types import DecisionResult, DistillResult


class RobotBrain:
    def decide(self, distill: DistillResult) -> DecisionResult:
        raise NotImplementedError


class FinRobotAdapter(RobotBrain):
    """Adapter that routes decisions to FinRobot when enabled."""
    def decide(self, distill: DistillResult) -> DecisionResult:
        if os.getenv("FINROBOT_ENABLED", "0") != "1":
            return self._fallback(distill)

        vendor_root = os.path.join(os.getcwd(), "vendor")
        if vendor_root not in sys.path:
            sys.path.append(vendor_root)

        try:
            import autogen
            from finrobot.agents.workflow import SingleAssistant
            from finrobot.utils import register_keys_from_json
        except Exception as exc:
            return DecisionResult(
                decision="Review",
                rationale=f"FinRobot import failed: {exc}",
                actions=[{"type": "request_more_info", "priority": "medium"}],
                approvals=[{"role": "analyst", "required": True}],
            )

        config_path = os.getenv("FINROBOT_OAI_CONFIG", "OAI_CONFIG_LIST")
        api_keys_path = os.getenv("FINROBOT_API_KEYS", "config_api_keys")
        if os.path.exists(api_keys_path):
            register_keys_from_json(api_keys_path)

        llm_config = {
            "config_list": autogen.config_list_from_json(
                config_path,
                filter_dict={"model": [os.getenv("FINROBOT_MODEL", "gpt-4-0125-preview")]},
            ),
            "timeout": 120,
            "temperature": 0.2,
        }

        message = self._build_message(distill)

        try:
            assistant = SingleAssistant(
                "Market_Analyst",
                llm_config,
                human_input_mode="NEVER",
                max_consecutive_auto_reply=6,
            )
            assistant.chat(message)
        except Exception as exc:
            return DecisionResult(
                decision="Review",
                rationale=f"FinRobot execution failed: {exc}",
                actions=[{"type": "request_more_info", "priority": "medium"}],
                approvals=[{"role": "analyst", "required": True}],
            )

        return DecisionResult(
            decision="Review",
            rationale="FinRobot chat executed. Review agent output logs.",
            actions=[{"type": "review_agent_output", "priority": "high"}],
            approvals=[{"role": "analyst", "required": True}],
        )

    def _build_message(self, distill: DistillResult) -> str:
        facts = distill.facts[:20]
        facts_lines = "\n".join([f"- {f}" for f in facts])
        cot = distill.cot_markdown[:2000]
        return (
            "You are FinRobot. Use the extracted facts and CoT to produce a decision summary.\n\n"
            "Facts (sample):\n"
            f"{facts_lines}\n\n"
            "CoT (excerpt):\n"
            f"{cot}\n\n"
            "Return a concise decision with risks and recommended actions."
        )

    def _fallback(self, distill: DistillResult) -> DecisionResult:
        rationale = "Auto-generated decision based on extracted facts."
        if distill.metadata.get("summary"):
            rationale = distill.metadata.get("summary")
        return DecisionResult(
            decision="Review",
            rationale=rationale,
            actions=[{"type": "request_more_info", "priority": "medium"}],
            approvals=[{"role": "analyst", "required": True}],
        )
