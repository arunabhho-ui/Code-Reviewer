import ast
import hashlib
import math
import re
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


@dataclass
class CodeChunk:
    chunk_id: str
    file_path: str
    symbol_name: str
    symbol_type: str  # "function" | "class" | "method" | "module"
    language: str
    code: str
    line_start: int
    line_end: int
    calls: List[str]
    bases: List[str]
    docstring: Optional[str] = None


class FastCodeEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Lightweight, deterministic, zero-external-download embedding function for code symbols.
    Hashes token n-grams and symbol names into a normalized 64-dimensional feature vector.
    Executes in < 0.5ms with 0 network dependencies.
    """
    def __init__(self, dim: int = 64):
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for doc in input:
            vec = [0.0] * self.dim
            tokens = re.findall(r"[a-zA-Z0-9_$]+", doc.lower())
            for t in tokens:
                # MD5 hash token into bucket
                h = int(hashlib.md5(t.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % self.dim
                vec[idx] += 1.0
            # L2 normalize
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings


# Singleton Chroma client and embedding instance
_chroma_client = None
_embedding_fn = FastCodeEmbeddingFunction()


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client(
            ChromaSettings(anonymized_telemetry=False, is_persistent=False)
        )
    return _chroma_client


def chunk_python_file(code: str, file_path: str) -> List[CodeChunk]:
    """
    Chunks Python code at AST symbol granularity (functions, async functions, classes).
    Extracts callers, inheritance bases, and exact line bounds.
    """
    chunks: List[CodeChunk] = []
    lines = code.splitlines()

    try:
        tree = ast.parse(code, filename=file_path)
    except SyntaxError:
        return [
            CodeChunk(
                chunk_id=f"{file_path}:module",
                file_path=file_path,
                symbol_name=file_path.split("/")[-1],
                symbol_type="module",
                language="python",
                code=code,
                line_start=1,
                line_end=len(lines),
                calls=[],
                bases=[],
            )
        ]

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start + len(node.body))
            chunk_code = "\n".join(lines[start - 1 : end])

            calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        calls.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.append(child.func.attr)

            docstring = ast.get_docstring(node)
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}:{node.name}:{start}",
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    language="python",
                    code=chunk_code,
                    line_start=start,
                    line_end=end,
                    calls=list(set(calls)),
                    bases=[],
                    docstring=docstring,
                )
            )

        elif isinstance(node, ast.ClassDef):
            start = node.lineno
            end = getattr(node, "end_lineno", start + len(node.body))
            chunk_code = "\n".join(lines[start - 1 : end])

            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)

            calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        calls.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.append(child.func.attr)

            docstring = ast.get_docstring(node)
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}:{node.name}:{start}",
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    language="python",
                    code=chunk_code,
                    line_start=start,
                    line_end=end,
                    calls=list(set(calls)),
                    bases=bases,
                    docstring=docstring,
                )
            )

    if not chunks and code.strip():
        chunks.append(
            CodeChunk(
                chunk_id=f"{file_path}:module",
                file_path=file_path,
                symbol_name=file_path.split("/")[-1],
                symbol_type="module",
                language="python",
                code=code,
                line_start=1,
                line_end=len(lines),
                calls=[],
                bases=[],
            )
        )

    return chunks


def chunk_javascript_file(code: str, file_path: str) -> List[CodeChunk]:
    """
    Chunks JavaScript/TypeScript code at function and class granularity using structural patterns.
    """
    chunks: List[CodeChunk] = []
    lines = code.splitlines()

    func_pattern = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)", re.MULTILINE)
    arrow_pattern = re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.MULTILINE)
    class_pattern = re.compile(r"^(?:export\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?", re.MULTILINE)

    for i, line in enumerate(lines, 1):
        m_func = func_pattern.search(line)
        if m_func:
            name = m_func.group(1)
            end_line = min(len(lines), i + 30)
            chunk_code = "\n".join(lines[i - 1 : end_line])
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}:{name}:{i}",
                    file_path=file_path,
                    symbol_name=name,
                    symbol_type="function",
                    language="javascript",
                    code=chunk_code,
                    line_start=i,
                    line_end=end_line,
                    calls=[],
                    bases=[],
                )
            )

        m_arrow = arrow_pattern.search(line)
        if m_arrow:
            name = m_arrow.group(1)
            end_line = min(len(lines), i + 25)
            chunk_code = "\n".join(lines[i - 1 : end_line])
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}:{name}:{i}",
                    file_path=file_path,
                    symbol_name=name,
                    symbol_type="function",
                    language="javascript",
                    code=chunk_code,
                    line_start=i,
                    line_end=end_line,
                    calls=[],
                    bases=[],
                )
            )

        m_class = class_pattern.search(line)
        if m_class:
            name = m_class.group(1)
            base = m_class.group(2)
            end_line = min(len(lines), i + 50)
            chunk_code = "\n".join(lines[i - 1 : end_line])
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}:{name}:{i}",
                    file_path=file_path,
                    symbol_name=name,
                    symbol_type="class",
                    language="javascript",
                    code=chunk_code,
                    line_start=i,
                    line_end=end_line,
                    calls=[],
                    bases=[base] if base else [],
                )
            )

    if not chunks and code.strip():
        chunks.append(
            CodeChunk(
                chunk_id=f"{file_path}:module",
                file_path=file_path,
                symbol_name=file_path.split("/")[-1],
                symbol_type="module",
                language="javascript",
                code=code,
                line_start=1,
                line_end=len(lines),
                calls=[],
                bases=[],
            )
        )

    return chunks


def chunk_file(code: str, file_path: str, language: str) -> List[CodeChunk]:
    """Unified AST / symbol chunker dispatch."""
    if language.lower() == "python":
        return chunk_python_file(code, file_path)
    if language.lower() in ("javascript", "typescript"):
        return chunk_javascript_file(code, file_path)

    # C and Java use a conservative symbol chunker until language-specific AST
    # parsers are introduced; preserving whole-file context is safer than
    # dropping supported files from the repository index.
    lines = code.splitlines()
    chunks: List[CodeChunk] = []
    symbol_pattern = re.compile(
        r"(?:^|\s)(?:class|struct|enum|interface)\s+([A-Za-z_]\w*)|"
        r"(?:^|\s)[A-Za-z_][\w<>:*&\[\], ]*\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
    )
    for index, line in enumerate(lines):
        match = symbol_pattern.search(line)
        if not match:
            continue
        symbol_name = match.group(1) or match.group(2)
        chunks.append(CodeChunk(
            chunk_id=f"{file_path}:{symbol_name}:{index + 1}",
            file_path=file_path,
            symbol_name=symbol_name,
            symbol_type="class" if match.group(1) else "function",
            language=language,
            code="\n".join(lines[index:]),
            line_start=index + 1,
            line_end=len(lines),
            calls=[],
            bases=[],
        ))

    if not chunks and code.strip():
        chunks.append(CodeChunk(
            chunk_id=f"{file_path}:module",
            file_path=file_path,
            symbol_name=file_path.split("/")[-1],
            symbol_type="module",
            language=language,
            code=code,
            line_start=1,
            line_end=len(lines),
            calls=[],
            bases=[],
        ))
    return chunks


def sanitize_collection_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if len(clean) < 3:
        clean = f"repo_{clean}"
    return clean[:60]


def index_repository_files(
    repo_name: str,
    files: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Indexes a collection of repository files into ChromaDB.
    Chunks files at function/class symbol granularity.
    """
    start_time = time.time()
    client = get_chroma_client()
    collection_name = sanitize_collection_name(repo_name)

    # Reset or create collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        embedding_function=_embedding_fn,
        metadata={"repo_name": repo_name, "created_at": time.time()}
    )

    all_chunks: List[CodeChunk] = []
    for f in files:
        path = f.get("path") or f.get("filename") or "file.py"
        content = f.get("content", "")
        lang = f.get("language") or (
            "python" if path.endswith(".py") else
            "typescript" if path.endswith((".ts", ".tsx")) else
            "c" if path.endswith((".c", ".h")) else
            "java" if path.endswith(".java") else
            "javascript"
        )
        chunks = chunk_file(content, path, lang)
        all_chunks.extend(chunks)

    if all_chunks:
        ids = [c.chunk_id for c in all_chunks]
        documents = [
            f"File: {c.file_path}\nSymbol: {c.symbol_name} ({c.symbol_type})\nCalls: {', '.join(c.calls)}\nBases: {', '.join(c.bases)}\n\n{c.code}"
            for c in all_chunks
        ]
        metadatas = [
            {
                "file_path": c.file_path,
                "symbol_name": c.symbol_name,
                "symbol_type": c.symbol_type,
                "language": c.language,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "calls_str": ",".join(c.calls),
                "bases_str": ",".join(c.bases),
            }
            for c in all_chunks
        ]

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    symbols = [f"{c.symbol_name} ({c.symbol_type} in {c.file_path})" for c in all_chunks]

    return {
        "repo_name": repo_name,
        "collection_name": collection_name,
        "total_files": len(files),
        "total_chunks": len(all_chunks),
        "symbols_indexed": symbols,
        "duration_ms": elapsed_ms,
    }


def retrieve_cross_file_context(
    repo_name: str,
    target_file_path: str,
    target_code: str,
    language: str,
    top_k: int = 4,
) -> List[Dict[str, Any]]:
    """
    Given a target file under review, retrieves cross-file context chunks from ChromaDB.
    """
    client = get_chroma_client()
    collection_name = sanitize_collection_name(repo_name)

    try:
        collection = client.get_collection(
            collection_name,
            embedding_function=_embedding_fn
        )
    except Exception:
        return []

    # Extract target file invoked symbols and class definitions
    target_chunks = chunk_file(target_code, target_file_path, language)
    invoked_calls = set()
    inherited_bases = set()
    for tc in target_chunks:
        invoked_calls.update(tc.calls)
        inherited_bases.update(tc.bases)

    query_terms = list(invoked_calls.union(inherited_bases))
    query_text = f"Functions: {' '.join(query_terms)}\nCode:\n{target_code[:500]}"

    results = collection.query(
        query_texts=[query_text],
        n_results=min(top_k * 2, max(1, collection.count())),
    )

    relevant_chunks = []
    if results and "documents" in results and results["documents"]:
        docs = results["documents"][0]
        metas = results["metadatas"][0] if "metadatas" in results else []

        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            chunk_file_path = meta.get("file_path", "")

            # Exclude chunks from the target file itself
            if chunk_file_path == target_file_path:
                continue

            symbol_name = meta.get("symbol_name", "symbol")
            symbol_type = meta.get("symbol_type", "function")

            relevance_reason = "Semantic code dependency"
            if symbol_name in invoked_calls:
                relevance_reason = f"Target file directly calls `{symbol_name}()`"
            elif symbol_name in inherited_bases:
                relevance_reason = f"Target file inherits from `{symbol_name}`"

            relevant_chunks.append({
                "file_path": chunk_file_path,
                "symbol_name": symbol_name,
                "symbol_type": symbol_type,
                "language": meta.get("language", language),
                "line_start": meta.get("line_start", 1),
                "line_end": meta.get("line_end", 1),
                "code_chunk": doc,
                "relevance_reason": relevance_reason,
            })

            if len(relevant_chunks) >= top_k:
                break

    return relevant_chunks
