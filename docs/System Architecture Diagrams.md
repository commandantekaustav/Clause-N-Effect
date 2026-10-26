# Clause-n-Effect: Deep-Dive System Architecture & Security Specification

This document specifies the internal state transitions, cryptographic threat boundaries, and self-evolving feedback loops of **Clause-n-Effect**.

---

## 1. End-to-End Sequence & Cryptographic Boundary

The system enforces a strict separation between **Local Trusted Memory (RAM)** and **Untrusted Cloud Storage (Pinecone)**.

```mermaid
sequenceDiagram
    autonumber
    participant User as Auditor / User
    participant Scrubber as PII Scrubber (Local RAM)
    participant Router8B as 8B Forensic Extractor
    participant CRAG as FAISS + CRAG Gate
    participant Reasoner70B as 70B Statutory Reasoner
    participant Critic8B as 8B Adversarial Judge
    participant Crypto as Fernet Crypto Engine (Local RAM)
    participant Pinecone as Pinecone Cloud Vector DB

    User->>Scrubber: Upload Contract PDF / Raw Clauses
    Scrubber->>Scrubber: Redact Names, PAN, Aadhaar, Emails, Salaries
    Scrubber->>Router8B: Sanitized Contract Text
    Router8B->>CRAG: Extracted Legal Entities & Clause Vectors
    alt Local FAISS Similarity >= Threshold
        CRAG->>Reasoner70B: Verified Statutory Context (ID Act / Contract Act / POSH)
    else Local FAISS Similarity < Threshold
        CRAG->>CRAG: Trigger Deterministic Web Search Fallback
        CRAG->>Reasoner70B: Augmented Statutory Context
    end
    Reasoner70B->>Critic8B: Draft Compliance Audit & Statutory Citations
    alt Critic Detects Hallucination / Missing Section
        Critic8B->>Reasoner70B: Reject Draft + Update dynamic_config.json
    else Critic Validates Statutory Grounding
        Critic8B->>Crypto: Approved Audit Payload
        Crypto->>Crypto: Encrypt Metadata Payload (Fernet AES-128-CBC + HMAC)
        Crypto->>Pinecone: Upsert (384-d Vector + Encrypted Ciphertext Payload)
        Critic8B->>User: Render Final Audit + Append Telemetry to track.json
    end
```

---

## 2. Threat Model: Vector Inversion vs. Payload Confidentiality

A common flaw in enterprise RAG systems is assuming that encrypting database disks protects vector payloads. **Clause-n-Effect** addresses two distinct threat vectors:

1. **Payload Confidentiality at Rest & in Transit (`Fernet`):**
   - Before any validated legal analysis leaves the local execution environment for Pinecone, the text metadata is encrypted using symmetric `Fernet` (`cryptography.fernet`), guaranteeing **AES-128 in CBC mode** with a **SHA256 HMAC** authentication tag.
   - If the Pinecone API key or cloud index is compromised, attackers obtain only ciphertext (`gAAAAAB...`) and cannot reconstruct the audited legal text without the local `FERNET_SECRET_KEY`.
2. **Mitigating Embedding Inversion Attacks (Upstream PII Scrubbing):**
   - Because vector similarity search requires mathematical plaintext embeddings ($v \in \mathbb{R}^{384}$ via `all-MiniLM-L6-v2`), raw embeddings remain vulnerable to gradient-based embedding inversion attacks.
   - **Defense-in-Depth:** The **PII Scrubber Node** executes *prior* to both embedding generation and LLM inference, replacing sensitive identifiers (`[PARTY_A]`, `[COMPENSATION_REDACTED]`, `[GOV_ID]`) so that neither the 384-dimensional vector nor the cloud LLM context ever encodes personally identifiable data.

---

## 3. Adversarial Actor-Critic & Self-Evolving Telemetry

To prevent open-ended retry loops and memory exhaustion on local hardware (8GB–24GB RAM ceiling):
- **Bounded Iteration Cap:** The `Router8B -> Reasoner70B -> Critic8B` cycle is strictly capped at a maximum of **2 self-correction retries** per clause batch.
- **Persistent Heuristic Evolution (`dynamic_config.json`):** When the 8B Judge flags a structural error (e.g., conflating "workman" definitions under Section 2(s) of the Industrial Disputes Act with managerial staff under the Indian Contract Act), it appends a concise negative constraint to `dynamic_config.json`, immunizing subsequent runs without fine-tuning overhead.
- **Deterministic Telemetry (`track.json`):** Records execution timestamps, token compression ratios, CRAG fallback triggers, and pass/fail verdicts for audit reproducibility.

## 4. Zero-Trust Memory Boundary (`Local RAM` vs. `Untrusted Cloud`)

```mermaid
flowchart LR
    subgraph Local_Trusted_Zone ["Local Volatile RAM (8GB-24GB Envelope) — TRUSTED"]
        direction TB
        RawPDF["Raw Contract PDF\n(Contains PII & Salaries)"] --> Scrubber["Regex + NER PII Scrubber"]
        Scrubber --> Sanitized["Sanitized Clauses\n([PARTY_A], [REDACTED])"]
        Sanitized --> Embedder["FAISS / MiniLM-L6-v2\n(<450MB RSS)"]
        Sanitized --> FernetEnc["Fernet AES-128-CBC + HMAC\n(Uses Local .env Key)"]
    end

    subgraph Cloud_Untrusted_Zone ["External Cloud Infrastructure — UNTRUSTED"]
        direction TB
        GroqAPI["70B / 8B Inference API\n(Sees Sanitized Text Only)"]
        PineconeDB[("Pinecone Vector Index\n384-d Float Vector + Fernet Ciphertext")]
    end

    Sanitized -->|"Zero Raw PII"| GroqAPI
    Embedder -->|"Plaintext 384-d Vector Only"| PineconeDB
    FernetEnc -->|"Ciphertext (gAAAAAB...)"| PineconeDB
```

---

## 5. Bounded Adversarial Actor-Critic State Machine (`stateDiagram-v2`)

```mermaid
stateDiagram-v2
    [*] --> Forensic_Compression_8B: Sanitized Clauses
    Forensic_Compression_8B --> CRAG_Retrieval: Extracted Entities

    state CRAG_Retrieval {
        [*] --> Local_FAISS_Query
        Local_FAISS_Query --> Score_Check
        Score_Check --> Statutory_Context: Cosine >= 0.72
        Score_Check --> Web_Fallback_Scrape: Cosine < 0.72
        Web_Fallback_Scrape --> Statutory_Context
    }

    CRAG_Retrieval --> Reasoner_70B: Grounded Statutes + dynamic_config.json
    Reasoner_70B --> Critic_8B_Judge: Draft Compliance Audit

    state Critic_Evaluation <<choice>>
    Critic_8B_Judge --> Critic_Evaluation

    Critic_Evaluation --> Patch_Dynamic_Config: Hallucination / Uncited Act (retry_count < 2)
    Patch_Dynamic_Config --> Reasoner_70B: Inject Negative Constraint

    Critic_Evaluation --> Deterministic_Fallback_Warning: Max Retries Reached (retry_count == 2)
    Critic_Evaluation --> Fernet_Flywheel_Upsert: Audit Verified (Pass)

    Deterministic_Fallback_Warning --> Emit_Audit_Telemetry
    Fernet_Flywheel_Upsert --> Emit_Audit_Telemetry
    Emit_Audit_Telemetry --> [*]: Write track.json
```