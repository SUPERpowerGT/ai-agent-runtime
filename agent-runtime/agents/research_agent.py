from agents.base_agent import BaseAgent
from runtime.services.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from runtime.services.documents import load_supported_documents, retrieve_relevant_chunks
from runtime.services.languages import extract_behavior_summaries, extract_code_contracts
from state.state import TaskState


class ResearchAgent(BaseAgent):
    """
    ResearchAgent 负责检索外部信息并提炼为可供后续 agent 使用的上下文。
    """

    name = "research"
    description = "Search the web and summarize relevant context"

    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry

    def _get_tool_registry(self):
        if self.tool_registry is None:
            from runtime.bootstrap.tools import init_tools

            self.tool_registry = init_tools()

        return self.tool_registry

    # --------------------------------------------------
    # Lifecycle Hooks
    # --------------------------------------------------

    def before_run(self, state: TaskState):
        log_agent(self.name, "starting")

        state.add_trace(
            agent_name=self.name,
            stage="before_run",
            message="research agent started",
        )

    def after_run(self, state: TaskState):
        state.add_trace(
            agent_name=self.name,
            stage="after_run",
            message="research agent finished",
        )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        documents = load_supported_documents(state.uploaded_files)
        retrieved_documents = retrieve_relevant_chunks(
            query=state.user_request,
            documents=documents,
            top_k=4,
        )
        code_contracts = extract_code_contracts(documents)
        behavior_summaries = extract_behavior_summaries(documents)

        return {
            "state": state,
            "query": state.user_request,
            "user_request": state.user_request,
            "documents": documents,
            "retrieved_documents": retrieved_documents,
            "code_contracts": code_contracts,
            "behavior_summaries": behavior_summaries,
        }

    def think(self, observation):
        query = observation["query"]

        web_search_tool = self._get_tool_registry().get("web_search")
        results = web_search_tool.run(query=query)
        document_context = observation["retrieved_documents"]
        code_contracts = observation["code_contracts"]
        behavior_summaries = observation["behavior_summaries"]

        prompt = f"""
You are the research agent in a multi-agent runtime.

Your role is ONLY to gather and summarize useful background context.
Do NOT write final code.
Do NOT propose a finished solution.
Do NOT include a complete solution or a copy-paste-ready final answer.
Do NOT include markdown code fences.
Do NOT include full code snippets unless a snippet is absolutely necessary to explain an API or syntax detail.

Focus on:
- relevant facts from the search results
- important syntax or API details
- constraints or implementation hints

Keep the summary short and practical.

User request:
{observation["user_request"]}

Task mode:
{observation["state"].task_spec.get("task_mode", "generate")}

Relevant user documents:
{document_context or "No uploaded documents matched the query."}

Extracted code contracts:
{code_contracts or "No language-specific code contracts were extracted from uploaded files."}

Extracted behavior summaries:
{behavior_summaries or "No language-specific behavior summaries were extracted from uploaded files."}

Search results:
{results}

Return ONLY a concise plain-text summary for another agent to use.
"""

        summary = call_llm(prompt, state=observation["state"], agent_name=self.name)

        return {
            "results": results,
            "summary": summary,
            "retrieved_documents": document_context,
            "code_contracts": code_contracts,
            "behavior_summaries": behavior_summaries,
        }

    def act(self, decision, state: TaskState) -> TaskState:
        results = decision["results"]
        summary = decision["summary"]
        retrieved_documents = decision["retrieved_documents"]
        code_contracts = decision["code_contracts"]
        behavior_summaries = decision["behavior_summaries"]

        if "research_raw" not in state.artifacts:
            state.artifacts["research_raw"] = []

        state.artifacts["research_raw"].extend(results)
        state.retrieved_documents = retrieved_documents
        state.rag_context = [item["text"] for item in retrieved_documents]
        state.artifacts["code_contracts"] = code_contracts
        state.artifacts["behavior_summaries"] = behavior_summaries
        state.task_spec["code_contracts"] = code_contracts
        state.task_spec["behavior_summaries"] = behavior_summaries
        state.working_memory["research"] = summary
        state.retrieved_context = [item.get("snippet", "") for item in results if item.get("snippet")]
        state.record_agent_output(self.name, summary)

        self.advance_to_next_planned_agent(state)

        log_agent(self.name, f"summary={preview_text(summary)}")
        log_agent(self.name, f"results={len(results)}")
        log_agent(self.name, f"doc_hits={len(retrieved_documents)}")
        log_agent(self.name, f"contracts={len(code_contracts)}")
        log_agent(self.name, f"behaviors={len(behavior_summaries)}")

        return state

    # --------------------------------------------------
    # Output Validation
    # --------------------------------------------------

    def validate_output(self, decision):
        if not isinstance(decision, dict):
            raise ValueError("research decision must be a dict")

        if (
            "results" not in decision
            or "summary" not in decision
            or "retrieved_documents" not in decision
            or "code_contracts" not in decision
            or "behavior_summaries" not in decision
        ):
            raise ValueError("research decision missing required fields")

        summary = decision["summary"].strip()

        prefixes = [
            "Here's a concise plain-text summary of the search results:",
            "Here is a concise plain-text summary of the search results:",
            "Here's a concise plain-text summary:",
            "Here is a concise plain-text summary:",
            "Here's a concise summary:",
            "Here is a concise summary:",
            "Summary:",
        ]

        for prefix in prefixes:
            if summary.startswith(prefix):
                summary = summary[len(prefix):].strip()
                break

        summary = summary.replace("```python", "").replace("```", "").strip()

        cleaned_lines = []
        for line in summary.splitlines():
            stripped = line.strip()

            if not stripped:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue

            if stripped.lower().startswith("def "):
                continue

            cleaned_lines.append(stripped)

        cleaned_summary = "\n".join(cleaned_lines).strip()

        if not cleaned_summary:
            raise ValueError("research summary is empty after cleaning")

        decision["summary"] = cleaned_summary

        return decision
