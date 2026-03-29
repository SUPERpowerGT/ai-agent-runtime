from agents.base_agent import BaseAgent
from agents.prompts import render_prompt
from observability.logging import log_agent, preview_text
from runtime.services.llm import call_llm
from runtime.services.languages import extract_behavior_summaries, extract_code_contracts
from state.read_context import StateReadPolicy
from state.state import TaskState


class ResearchAgent(BaseAgent):
    """
    ResearchAgent 负责检索外部信息并提炼为可供后续 agent 使用的上下文。
    """

    name = "research"
    description = "Search the web and summarize relevant context"
    allowed_skills = ["rag_retrieve", "web_search"]
    before_run_trace_message = "research agent started"
    after_run_trace_message = "research agent finished"
    state_read_policy = StateReadPolicy(
        conversation_message_limit=4,
        history_limit=3,
        memory_keys=("user_id", "conversation_id", "session_summary", "preference", "last_success_summary"),
        memory_max_items=6,
        memory_max_chars=500,
    )

    # --------------------------------------------------
    # Core Agent Stages
    # --------------------------------------------------

    def perceive(self, state: TaskState):
        read_context = self.build_state_read_context(state)
        active_request = read_context.latest_user_message
        preloaded_documents = state.retrieved_documents or []
        using_external_rag = bool(preloaded_documents)
        existing_code_contracts = list(state.task_spec.get("code_contracts", []))
        existing_behavior_summaries = list(state.task_spec.get("behavior_summaries", []))

        documents: list[dict] = []
        retrieved_documents = preloaded_documents
        context_blocks: list[dict] = []
        citations: list[dict] = []
        query_analysis: dict = {}
        retrieval_metadata: dict = {}
        code_contracts: list[dict] = []
        behavior_summaries: list[dict] = []

        if not using_external_rag:
            rag_result = self.use_skill(
                state,
                "rag_retrieve",
                query=active_request,
                uploaded_files=state.uploaded_files,
                top_k=4,
            )
            documents = rag_result["documents"]
            retrieved_documents = rag_result["retrieved_documents"]
            context_blocks = rag_result["context_blocks"]
            citations = rag_result["citations"]
            query_analysis = rag_result["query_analysis"]
            retrieval_metadata = rag_result["retrieval_metadata"]
            code_contracts = rag_result["code_contracts"]
            behavior_summaries = rag_result["behavior_summaries"]
        else:
            rag_source_documents = [
                {
                    "source": item.get("source", "external-rag"),
                    "text": item.get("text", ""),
                }
                for item in preloaded_documents
                if item.get("text")
            ]
            context_blocks = [
                {
                    "id": f"context-{index}",
                    "source": item.get("source", "external-rag"),
                    "chunk_id": item.get("chunk_id", ""),
                    "text": item.get("text", ""),
                    "score": item.get("score", 0.0),
                }
                for index, item in enumerate(preloaded_documents, start=1)
            ]
            citations = [
                {
                    "id": block["id"],
                    "source": block["source"],
                    "chunk_id": block["chunk_id"],
                    "score": block["score"],
                }
                for block in context_blocks
            ]
            query_analysis = {
                "original_query": active_request,
                "normalized_query": active_request,
                "rewritten_queries": [active_request],
                "query_terms": [],
            }
            retrieval_metadata = {
                "documents_loaded": len(rag_source_documents),
                "documents_cleaned": len(rag_source_documents),
                "chunks_created": len(preloaded_documents),
                "documents_retrieved": len(preloaded_documents),
            }
            code_contracts = extract_code_contracts(rag_source_documents)
            behavior_summaries = extract_behavior_summaries(rag_source_documents)

        return self.build_prompt_observation(
            state,
            query=active_request,
            documents=documents,
            retrieved_documents=retrieved_documents,
            context_blocks=context_blocks,
            citations=citations,
            query_analysis=query_analysis,
            retrieval_metadata=retrieval_metadata,
            code_contracts=code_contracts,
            behavior_summaries=behavior_summaries,
            existing_code_contracts=existing_code_contracts,
            existing_behavior_summaries=existing_behavior_summaries,
            using_external_rag=using_external_rag,
        )

    def think(self, observation):
        query = observation["query"]

        results = self.use_skill(
            observation["state"],
            "web_search",
            query=query,
        )
        document_context = observation["retrieved_documents"]
        context_blocks = observation["context_blocks"]
        citations = observation["citations"]
        code_contracts = observation["code_contracts"] or observation["existing_code_contracts"]
        behavior_summaries = observation["behavior_summaries"] or observation["existing_behavior_summaries"]
        using_external_rag = observation["using_external_rag"]

        prompt = render_prompt(
            "research_summary",
            user_request=observation["user_request"],
            latest_user_message=observation["latest_user_message"],
            conversation_context=observation["conversation_context"] or "No prior conversation context.",
            history_context=observation["history_context"] or "No archived turn history.",
            memory_context=observation["memory_context"] or "No session memory.",
            task_mode=observation["state"].task_spec.get("task_mode", "generate"),
            document_context=context_blocks or document_context or "No uploaded documents matched the query.",
            retrieval_source=(
                "External RAG context supplied by the caller."
                if using_external_rag
                else "Runtime local file retrieval from uploaded documents."
            ),
            citations=citations or "No citations available.",
            code_contracts=code_contracts or "No language-specific code contracts were extracted from uploaded files.",
            behavior_summaries=behavior_summaries or "No language-specific behavior summaries were extracted from uploaded files.",
            search_results=results,
        )

        summary = call_llm(prompt, state=observation["state"], agent_name=self.name)

        return {
            "results": results,
            "summary": summary,
            "retrieved_documents": document_context,
            "context_blocks": context_blocks,
            "citations": citations,
            "query_analysis": observation["query_analysis"],
            "retrieval_metadata": observation["retrieval_metadata"],
            "code_contracts": code_contracts,
            "behavior_summaries": behavior_summaries,
        }

    def act(self, decision, state: TaskState) -> TaskState:
        results = decision["results"]
        summary = decision["summary"]
        retrieved_documents = decision["retrieved_documents"]
        context_blocks = decision["context_blocks"]
        citations = decision["citations"]
        query_analysis = decision["query_analysis"]
        retrieval_metadata = decision["retrieval_metadata"]
        code_contracts = decision["code_contracts"]
        behavior_summaries = decision["behavior_summaries"]

        if "research_raw" not in state.artifacts:
            state.artifacts["research_raw"] = []

        state.artifacts["research_raw"].extend(results)
        state.retrieved_documents = retrieved_documents
        if context_blocks:
            state.rag_context = [item.get("text", "") for item in context_blocks if item.get("text")]
        elif retrieved_documents:
            state.rag_context = [item.get("text", "") for item in retrieved_documents if item.get("text")]
        state.artifacts["rag_context_blocks"] = context_blocks
        state.artifacts["rag_citations"] = citations
        state.artifacts["rag_query_analysis"] = query_analysis
        state.artifacts["rag_retrieval_metadata"] = retrieval_metadata
        state.artifacts["code_contracts"] = code_contracts
        state.artifacts["behavior_summaries"] = behavior_summaries
        state.task_spec["code_contracts"] = code_contracts
        state.task_spec["behavior_summaries"] = behavior_summaries
        state.local_memory["research"] = summary
        state.retrieved_context = [item.get("snippet", "") for item in results if item.get("snippet")]
        state.record_agent_output(self.name, summary)

        log_agent(self.name, f"summary={preview_text(summary)}")
        log_agent(self.name, f"results={len(results)}")
        log_agent(self.name, f"doc_hits={len(retrieved_documents)}")
        log_agent(self.name, f"context_blocks={len(context_blocks)}")
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
            or "context_blocks" not in decision
            or "citations" not in decision
            or "query_analysis" not in decision
            or "retrieval_metadata" not in decision
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
