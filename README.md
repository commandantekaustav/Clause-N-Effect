# Clause-n-Effect

> Deterministic Indian labor law & corporate compliance auditor powered by a hybrid-brain LangGraph state machine and a zero-trust cryptographic data flywheel.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Vector DB](https://img.shields.io/badge/Vector%20Store-Pinecone%20%7C%20FAISS-green.svg)](https://www.pinecone.io/)
[![Security](https://img.shields.io/badge/Security-Fernet%20AES--128--CBC-red.svg)](https://cryptography.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]([LICENSE](https://opensource.org/license/mit))

---

## The Manifesto: Destroying Corporate Information Asymmetry

In corporate ecosystems, legal ambiguity is weaponized against software engineers and freshers. Non-compete clauses, IP assignment overreach, arbitrary bond enforcement, and retaliatory PIPs thrive on one dynamic: **information asymmetry**. HR departments and corporate legal teams possess dedicated counsel; the individual engineer possesses only stress, isolated forum threads, and intimidation.

**Clause-n-Effect** is an open-source, deterministic, Zero-Trust legal compliance and forensic auditing engine built to level that playing field. It forensically audits contracts, offer letters, PIP mandates, and email chains Indian statutory law (**Industrial Disputes Act, Indian Contract Act, POSH Act, and Specific Relief Act**) grounding every counter-argument in binding statutory code and precedent, not generative hallucinations.

Built to eliminate the non-determinism, hallucination risk, and plaintext cloud data leaks of naive RAG wrappers, the system couples a **deterministic LangGraph state machine** with **Hybrid-Brain LLM routing (8B/70B)**, an **Adversarial Actor-Critic Judge loop**, and a **Fernet-encrypted Pinecone Data Flywheel**.

---

## Statutory Grounding

Audits are evaluated strictly against statutory frameworks and landmark judicial interpretations under Indian law:

| Statutory Framework | Audit Surface |
| :--- | :--- |
| **Indian Contract Act, 1872 (§ 27)** | Post-termination non-competes, unreasonable restraint of trade, liquidated damages vs. unconstitutional penalties. |
| **Industrial Disputes Act, 1947 (§ 2A, § 25F/N)** | Retrenchment protocols, wrongful termination under the guise of performance exits, operational severance mandates. |
| **Specific Relief Act, 1963 (§ 14, § 41)** | Unenforceability of specific performance for personal service contracts (preventing forced employment bonds). |
| **POSH Act, 2013** | Procedural compliance in Internal Committee (IC) constitution, inquiry timelines, and protection against retaliatory actions. |
| **Notable Verdicts**| You have complete relaxation over here albeit adequate knowledge of the legal and judiciary system as well as cetain domain expertise would be required to maintain the current optimal standards. 
---

## System Architecture & Deterministic State Flow

```mermaid
graph TD
    A[Raw Contract Text / Email Thead] --> B[Upstream PII Scrubber: Regex + NER Redaction]
    B --> C[Forensic Compression Node: Local/Fast 8B LLM]
    C --> D[Local Vector Retrieval: FAISS all-MiniLM-L6-v2]
    D --> E{CRAG Relevance Gate}
    E -->|High Confidence| F[Statutory Reasoning Node: 70B LLM]
    E -->|Low Confidence / Ambiguous| G[Web Search Fallback: Statutory Scraping]
    G --> F
    F --> H[Adversarial Critic Node: 8B Judge]
    H -->|Hallucination / Uncited Claim| I[Self-Correction & Prompt Patch: dynamic_config.json]
    I --> F
    H -->|Verified & Statutorily Grounded| J[Zero-Trust Flywheel: Fernet Payload Encryption]
    J --> K[(Pinecone Cloud Vector DB)]
    H --> L[Final Forensic Audit Report + track.json Telemetry]
```

*(For deep-dive sequence diagrams, cryptographic boundary specs, and memory-ceiling profiling, see **[docs/System Architecture Diagrams.md](docs/System%20Architecture%20Diagrams.md)**).*
---

## Core Engineering Decisions & Threat Model

| Architectural Layer | Implementation | Engineering Trade-Off & Quantitative Impact |
| :--- | :--- | :--- |
| **Hybrid-Brain Routing** | **8B Model** (Forensic Extraction) + **70B Model** (Statutory Reasoning) | Offloads high-token clause chunking and metadata extraction to a low-latency 8B model, reducing 70B token consumption by **~65%** and preventing context-window dilution. |
| **Corrective RAG (CRAG)** | Local `FAISS` (`all-MiniLM-L6-v2`) + Web Fallback | Keeps baseline statutory retrieval at **<50ms latency** and **<600MB RAM** locally; triggers deterministic web fallback only when cosine similarity drops below threshold. |
| **Zero-Trust Cloud Flywheel** | Upstream PII Scrubber + Symmetric `Fernet` (AES-128-CBC + HMAC-SHA256) | Cloud vector databases cannot be trusted with raw legal contracts. Text payloads are scrubbed of PII before embedding and encrypted via `Fernet` before Pinecone upsert, decrypted strictly in-memory (`RAM`) upon authorized fetch. |
| **Adversarial Actor-Critic** | 8B Constitutional Judge + `dynamic_config.json` | Intercepts 70B drafts containing uncited statutory claims or hallucinated sections (e.g., citing repealed labor provisions). Dynamically patches system rules in `dynamic_config.json` to prevent recurring failure modes. |
| **Observability & Telemetry** | Local `track.json` Execution Ledger | Logs node transition latencies, CRAG fallback frequency, and Critic rejection rates with zero external telemetry overhead. |

---

## Hardware & Memory Envelope

Engineered and benchmarked to run deterministically within an **8GB–24GB DDR4 RAM** local ceiling:
- **Local Embedding Footprint:** `sentence-transformers/all-MiniLM-L6-v2` (~90MB weights, <450MB peak process RSS).
- **Stateless Execution Boundaries:** All PDF parsing and `Fernet` cryptographic transforms execute in-memory with explicit garbage collection to prevent memory leaks across multi-document batches.


## Architectural Deep Dive

### 1. Hybrid-Brain Model Routing (Cost & Latency Optimization)
- **Fast / Forensic Node (`llama-3.1-8b-instant`)**: Handles regex-assisted forensic metadata extraction (`To`, `Cc`, `Bcc`, timestamps, organizational hierarchy), query compression, and fast semantic parsing.
- **Litigator Reasoning Node (`llama-3.3-70b-versatile`)**: Dedicated exclusively to statutory interpretation, cross-referencing multi-act liabilities, and drafting enforceable counter-responses.
- **Judge Node (`llama-3.1-8b-instant`)**: Evaluates litigator claims against statutory excerpts to enforce strict hallucination limits.

### 2. Zero-Trust Cryptographic Data Flywheel
- **Threat Model**: Standard cloud RAG pipelines store raw prompt payloads in vector store metadata. In multi-tenant cloud vector databases, a metadata leak compromises sensitive corporate documents, salary slips, and dispute logs. Furthermore, dense vector embeddings are susceptible to embedding inversion attacks.
- **Mitigation Pipeline**:
  1. **Pre-Vectorization Sanitization**: The input passes through a regex and NER-driven PII Scrubber *prior* to FAISS vectorization (`all-MiniLM-L6-v2`).
  2. **Client-Side Symmetric Encryption**: Validated "gold" reasoning payloads are symmetrically encrypted using `cryptography.fernet.Fernet` (AES-128-CBC with HMAC-SHA256 authentication) on the local runtime.
  3. **Cloud Storage Boundary**: Pinecone stores *only* the encrypted blob in its metadata. The decryption key resides exclusively in client memory; compromised vector store access yields zero actionable plaintext.

### 3. Adversarial Actor-Critic Loop
- Outputs do not proceed directly to the UI.
- The **Corporate-HR Defense Critic** node explicitly red-teams the Litigator's assessment by attempting to justify the disputed clause via internal policies, proprietary data exemptions, or managerial prerogative.
- The **8B Judge** compares the HR defense against the statutory citations. If the Litigator's statutory basis fails scrutiny, the state machine triggers a cyclic re-prompt (`max_retries=3`) before final emission.
- Telemetry is recorded locally to `track.json`, and prompt edge cases are captured into `dynamic_config.json` for prompt patch evolution.

---

## Repository Structure

```
Clause-n-Effect/
├── app.py                   # Streamlit UI & interactive audit dashboard
├── core/
│   ├── graph.py             # LangGraph state machine definition
│   ├── hybrid_brain.py      # 8B / 70B routing and Groq LLM client
│   ├── crypto.py            # Fernet symmetric encryption & Pinecone flywheel
│   ├── scrubber.py          # Pre-retrieval PII sanitization engine
│   └── rag.py               # Corrective RAG (FAISS + search fallback)
├── config/
│   ├── dynamic_config.json  # Self-evolving prompt patches & dynamic weights
│   └── statutes.json        # Indexed statutory citations and sections
├── telemetry/
│   └── track.json           # Execution telemetry and failure-mode tracking
├── requirements.txt         # Minimal production dependencies
└── .env.example             # Environment configuration template
```

---

## Quickstart

### 1. Prerequisites
- Python 3.10+
- Groq API Key
- Pinecone API Key (optional, for persistent encrypted flywheel)

### 2. Installation
```bash
git clone [https://github.com/commandantekaustav/Clause-n-Effect.git](https://github.com/commandantekaustav/Clause-n-Effect.git)
cd Clause-n-Effect
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Setup
```bash
cp .env.example .env
```
Populate `.env` with your credentials:
```env
GROQ_API_KEY=your_groq_api_key
GROQ_FAST_MODEL=llama-3.1-8b-instant
GROQ_REASONING_MODEL=llama-3.3-70b-versatile

# Zero-Trust Flywheel Encryption Key (generate via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
FERNET_SECRET_KEY=your_base64_fernet_key

# Pinecone Config (Optional)
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=clause-n-effect-gold
```

### 4. Run the Engine
```bash
streamlit run app.py
```

---

## Deterministic Verification

Run the core graph verification script to validate end-to-end PII scrubbing, model routing, and payload encryption without spinning up the UI:

```bash
python -m unittest tests/test_pipeline.py
```

---

## Roadmap

- [x] LangGraph deterministic workflow orchestration
- [x] Hybrid-Brain model routing (8B / 70B Groq inference)
- [x] Zero-Trust Fernet encryption flywheel on Pinecone
- [x] Upstream PII Scrubber
- [ ] Local fallback node powered by Ollama (`qwen2.5-coder`) for complete offline auditing
- [ ] Exportable statutory notice generator (PDF format with legal formatting standards)

---

## Paper Ref:
1. [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/pdf/2005.11401)
2. [Corrective Retrieval Augmented Generation](https://arxiv.org/pdf/2401.15884)

---
## License

Distributed under the MIT License. See `LICENSE` for details.
