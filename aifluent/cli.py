import argparse
import json
import time
from pathlib import Path

import requests

from aifluent.chat.service import ChatMessage
from aifluent.chat.service import chat_completion
from aifluent.chat.service import delete_chat_session
from aifluent.chat.service import list_chat_sessions
from aifluent.chat.service import load_chat_session
from aifluent.chat.service import save_chat_session
from aifluent.core.model_manager import ModelManager
from aifluent.core.agent import BaseAgent
from aifluent.core.swarm_orchestrator import SwarmOrchestrator
from aifluent.core.test_generator import TestGenerator
from aifluent.memory.config import get_default_memory_config
from aifluent.memory.store import Event, Store


def _existing_dir(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Directory not found: {path_str}")
    return path


def _existing_file(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {path_str}")
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AIFluent command line interface.",
        epilog=(
            "Examples:\n"
            "  aifluent analyze --repo .\n"
            "  aifluent refactor --file src/app.py\n"
            "  aifluent test --repo ./my-project\n"
            "  aifluent memory-add --kind note --data '{\"text\":\"reviewed PR\"}'\n"
            "  aifluent memory-search --query reviewed\n"
            "  aifluent chat --message 'Summarize this project'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze a repository.")
    analyze.add_argument("--repo", default=Path("."), type=_existing_dir, help="Repository path.")

    refactor = subparsers.add_parser("refactor", help="Suggest refactoring for one file.")
    refactor.add_argument("--repo", default=Path("."), type=_existing_dir, help="Repository path.")
    refactor.add_argument("--file", required=True, type=_existing_file, help="File to refactor.")

    test = subparsers.add_parser("test", help="Generate placeholder pytest files.")
    test.add_argument("--repo", default=Path("."), type=_existing_dir, help="Repository path.")

    memory_add = subparsers.add_parser("memory-add", help="Add one memory event.")
    memory_add.add_argument("--kind", required=True, help="Event kind, for example note or action.")
    memory_add.add_argument("--data", required=True, help="JSON object payload for the event.")
    memory_add.add_argument("--blob", default="", help="Optional blob reference.")
    memory_add.add_argument("--timestamp", type=float, default=None, help="Optional event timestamp.")

    memory_search = subparsers.add_parser("memory-search", help="Search stored memory events.")
    memory_search.add_argument("--query", required=True, help="Full-text query.")
    memory_search.add_argument("--kind", default=None, help="Optional event kind filter.")
    memory_search.add_argument("--limit", type=int, default=20, help="Maximum results.")

    subparsers.add_parser("memory-stats", help="Show memory store statistics.")

    chat = subparsers.add_parser("chat", help="Talk to the configured local model.")
    chat.add_argument("--message", default=None, help="Single-shot prompt. If omitted, starts interactive mode.")
    chat.add_argument("--model", default=None, help="Override the default active model.")
    chat.add_argument("--system", default=None, help="Optional system prompt.")
    chat.add_argument("--resume", default=None, help="Resume a saved chat session tag.")
    chat.add_argument("--list-sessions", action="store_true", help="List saved chat sessions.")
    chat.add_argument("--save", default=None, help="Save a one-shot chat or current interactive chat under this tag.")
    chat.add_argument("--delete", default=None, help="Delete a saved chat session tag.")

    subparsers.add_parser("collaborate", help="Show collaboration feature status.")
    return parser


def _build_runtime() -> tuple[BaseAgent, SwarmOrchestrator]:
    model_manager = ModelManager()
    model_manager.select_models()
    model_manager.load_active_models()
    agent = BaseAgent("Agent-1", model_manager)
    swarm = SwarmOrchestrator([agent], voting_threshold=model_manager.voting_threshold)
    return agent, swarm


def _memory_store() -> Store:
    cfg = get_default_memory_config()
    return Store(cfg.db_path)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "collaborate":
        print("[CLI] Multi-agent collaboration is not implemented yet.")
        return 0

    if args.command == "memory-add":
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as exc:
            parser.exit(status=2, message=f"error: invalid JSON for --data: {exc}\n")
        if not isinstance(data, dict):
            parser.exit(status=2, message="error: --data must decode to a JSON object\n")
        store = _memory_store()
        store.insert_raw([Event(timestamp=args.timestamp or time.time(), kind=args.kind, data=data, blob=args.blob)])
        print(f"[MEMORY] Stored event kind={args.kind}")
        return 0

    if args.command == "memory-search":
        store = _memory_store()
        results = store.search(args.query, kind=args.kind, limit=args.limit)
        print(json.dumps([{"id": e.id, "timestamp": e.timestamp, "kind": e.kind, "data": e.data, "blob": e.blob} for e in results], indent=2, ensure_ascii=False))
        return 0

    if args.command == "memory-stats":
        store = _memory_store()
        print(json.dumps(store.stats(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "chat":
        if args.list_sessions:
            print(json.dumps(list_chat_sessions(), indent=2, ensure_ascii=False))
            return 0

        if args.delete:
            try:
                delete_chat_session(args.delete)
            except FileNotFoundError as exc:
                parser.exit(status=2, message=f"error: {exc}\n")
            print(f"[CHAT] Deleted session {args.delete}")
            return 0

        if args.message:
            base_history: list[ChatMessage] = []
            if args.resume:
                try:
                    session = load_chat_session(args.resume)
                    base_history = [ChatMessage(role=item["role"], content=item["content"]) for item in session.get("messages", [])]
                except FileNotFoundError as exc:
                    parser.exit(status=2, message=f"error: {exc}\n")
            try:
                reply = chat_completion(
                    messages=base_history + [ChatMessage(role="user", content=args.message)],
                    model=args.model,
                    system_prompt=args.system,
                )
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                parser.exit(status=2, message=f"error: chat request failed: {exc}\n")
            if args.save:
                session_messages = base_history + [
                    ChatMessage(role="user", content=args.message),
                    ChatMessage(role=reply["message"]["role"], content=reply["message"]["content"]),
                ]
                save_chat_session(args.save, session_messages, model=reply["model"])
            print(reply["message"]["content"])
            return 0

        history: list[ChatMessage] = []
        if args.resume:
            try:
                session = load_chat_session(args.resume)
                history = [ChatMessage(role=item["role"], content=item["content"]) for item in session.get("messages", [])]
                print(f"[CHAT] Resumed {args.resume} with {len(history)} messages.")
            except FileNotFoundError as exc:
                parser.exit(status=2, message=f"error: {exc}\n")
        print("[CHAT] Interactive mode. Type /exit to quit, /clear to reset history, /save <tag>, /list, /resume <tag>.")
        while True:
            try:
                prompt = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("")
                return 0
            if not prompt:
                continue
            if prompt == "/exit":
                return 0
            if prompt == "/clear":
                history.clear()
                print("[CHAT] History cleared.")
                continue
            if prompt == "/list":
                print(json.dumps(list_chat_sessions(), indent=2, ensure_ascii=False))
                continue
            if prompt.startswith("/save "):
                tag = prompt.split(" ", 1)[1].strip()
                try:
                    path = save_chat_session(tag, history, model=args.model)
                except ValueError as exc:
                    print(f"error: {exc}")
                    continue
                print(f"[CHAT] Saved session '{tag}'.")
                continue
            if prompt.startswith("/resume "):
                tag = prompt.split(" ", 1)[1].strip()
                try:
                    session = load_chat_session(tag)
                except FileNotFoundError as exc:
                    print(f"error: {exc}")
                    continue
                history = [ChatMessage(role=item["role"], content=item["content"]) for item in session.get("messages", [])]
                print(f"[CHAT] Resumed {tag} with {len(history)} messages.")
                continue
            history.append(ChatMessage(role="user", content=prompt))
            try:
                reply = chat_completion(messages=history, model=args.model, system_prompt=args.system)
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                print(f"error: chat request failed: {exc}")
                continue
            content = reply["message"]["content"].strip()
            history.append(ChatMessage(role="assistant", content=content))
            print(f"assistant> {content}")
        return 0

    try:
        agent, swarm = _build_runtime()
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")

    if args.command == "analyze":
        agent.analyze_code(str(args.repo))
        return 0

    if args.command == "refactor":
        swarm.refactor_file(str(args.file))
        return 0

    if args.command == "test":
        tg = TestGenerator(str(args.repo))
        tg.generate_tests()
        return 0

    parser.exit(status=2, message=f"error: unsupported command '{args.command}'\n")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
