# **Clause-N-Effect: Architecture & System Design**

This document outlines the system architecture, data flows, detailed UMLs, and state machine diagrams for the Clause-N-Effect compliance engine. All diagrams are rendered using Mermaid.js, conforming to Docs-as-Code industry standards.

## **1\. High-Level System Architecture**

This diagram illustrates the macro-level interaction between the user interface, the LangGraph engine, the retrieval tools, and the telemetry layer.

graph TB  
    subgraph Frontend  
        UI\[Streamlit App \<br/\> \<code\>app.py\</code\>\]  
        UI\_State\[Session State: \<br/\> Token/Rate Limiter\]  
    end

    subgraph API Layer  
        Engine\[Agent Engine Entrypoint \<br/\> \<code\>agent\_engine.py\</code\>\]  
    end

    subgraph Core Orchestration  
        DAG\[LangGraph State Machine \<br/\> \<code\>src/agents/graph.py\</code\>\]  
        Prompts\[Prompt Registry \<br/\> \<code\>system\_prompts.py\</code\>\]  
    end

    subgraph Tooling & RAG  
        HybridRAG\[Hybrid Retriever \<br/\> FAISS \+ BM25 \+ CrossEncoder\]  
        WebSearch\[Tavily Web Search \<br/\> \<code\>search.py\</code\>\]  
        TextCrush\[Regex Text Crusher \<br/\> \<code\>text\_crusher.py\</code\>\]  
    end

    subgraph Data & Telemetry  
        DB\[(FAISS Local DB \<br/\> \<code\>faiss\_legal\_db/\</code\>)\]  
        Logs\[(Telemetry Logs \<br/\> \<code\>track.json\</code\>)\]  
    end

    %% Connections  
    UI \<--\>|User Query & HR Facts| UI\_State  
    UI\_State \<--\>|Validated Payload| Engine  
    Engine \--\> DAG  
    DAG \<--\> Prompts  
    DAG \<--\> HybridRAG  
    DAG \<--\> WebSearch  
    DAG \<--\> TextCrush  
    HybridRAG \<--\> DB  
    DAG \--\>|Transaction Metrics| Logs

    classDef core fill:\#2b313e,stroke:\#4caf50,stroke-width:2px,color:\#fff;  
    classDef frontend fill:\#0e1117,stroke:\#ff4b4b,stroke-width:2px,color:\#fff;  
    classDef tools fill:\#1e1e1e,stroke:\#2196f3,stroke-width:2px,color:\#fff;  
    classDef db fill:\#3e2723,stroke:\#ff9800,stroke-width:2px,color:\#fff;  
      
    class UI,UI\_State frontend;  
    class DAG,Engine core;  
    class HybridRAG,WebSearch,TextCrush tools;  
    class DB,Logs db;

## **2\. LangGraph State Machine (DAG)**

This diagram maps the exact routing logic, conditional edges, and the self-correcting Actor-Critic loop defined in graph.py.

stateDiagram-v2  
    direction TB  
      
    \[\*\] \--\> compress\_query: Start  
    compress\_query \--\> retrieve: Extract Meta & Facts (8B)  
    retrieve \--\> grade\_documents: Hybrid Context Fetch  
      
    state Grade\_Condition \<\<choice\>\>  
    grade\_documents \--\> Grade\_Condition: Grade Docs (8B)  
      
    Grade\_Condition \--\> web\_search: Score \== NO  
    Grade\_Condition \--\> draft\_corporate\_defense: Score \== YES  
      
    web\_search \--\> draft\_corporate\_defense: Fallback Context  
      
    draft\_corporate\_defense \--\> generate\_audit: Red Team Persona (8B)  
    generate\_audit \--\> evaluate\_audit: Synthesis (70B)  
      
    state Eval\_Condition \<\<choice\>\>  
    evaluate\_audit \--\> Eval\_Condition: LLM-as-a-Judge (8B)  
      
    Eval\_Condition \--\> generate\_audit: FAIL (Revisions \< 3\)  
    Eval\_Condition \--\> \[\*\]: PASS / (Revisions \>= 3\)

    note right of evaluate\_audit  
        Critic Node enforces  
        Markdown formatting and  
        HTML Span exact matches.  
    end note

## **3\. UML Class Diagram: State & Data Structures**

This UML Class Diagram outlines the strict typing, Pydantic models, and custom Python classes that enforce data integrity across the application.

classDiagram  
    class GraphState {  
        \<\<TypedDict\>\>  
        \+str question  
        \+List\[str\] documents  
        \+str web\_search\_context  
        \+str corporate\_defense  
        \+str generation  
        \+str judge\_score  
        \+str judge\_feedback  
        \+int revision\_count  
        \+List\[str\] steps  
    }

    class GradeResult {  
        \<\<Pydantic\>\>  
        \+str score  
    }

    class JudgeResult {  
        \<\<Pydantic\>\>  
        \+str score  
        \+str feedback  
    }

    class EvaluationScore {  
        \<\<Pydantic\>\>  
        \+int accuracy\_score  
        \+bool statute\_match  
        \+str reasoning  
    }

    class ContextualRerankingRetriever {  
        \<\<Custom Class\>\>  
        \+base\_retriever : Any  
        \+cross\_encoder : Any  
        \+top\_n : int  
        \+score\_threshold : float  
        \+invoke(query: str) List\[Any\]  
    }

    GraphState ..\> GradeResult : Validates via Node  
    GraphState ..\> JudgeResult : Validates via Node  
    ContextualRerankingRetriever \--\> GraphState : Feeds 'documents'

## **4\. Mail Indexer & Subtraction Matrix (Sequence Diagram)**

This sequence diagram illustrates the internal logic of mail\_indexer.py, specifically detailing how the Subtraction Matrix achieves deterministic deduplication of complex email threads.

sequenceDiagram  
    autonumber  
    participant PDF as Raw PDF (pypdf)  
    participant Indexer as mail\_indexer.py  
    participant Regex as Subtraction Matrix  
    participant Hash as Fingerprint Engine  
    participant MD as Markdown Output

    PDF-\>\>Indexer: extract\_text\_from\_pdf()  
    Indexer-\>\>Regex: split block array (Headers)  
      
    loop For each email block  
        Regex-\>\>Regex: Extract Metadata (Sender, Date, Subject)  
          
        Note over Regex: Phase 1: Truncate deduplication tails\<br/\>(e.g., "On X wrote:")  
        Regex-\>\>Regex: Split and take \[0\] index  
          
        Note over Regex: Phase 2: Subtract known entities\<br/\>(To, Cc, Sender, Subject)  
        Regex-\>\>Regex: Normalize & Vacuum Whitespace  
          
        Regex-\>\>Hash: Generate whitespace-free hash (lower())  
          
        alt Hash is Unique & length \> 5  
            Hash--\>\>Indexer: Add to seen\_contents set  
            Indexer-\>\>Indexer: Parse Date & append to parsed\_emails  
        else Hash exists in seen\_contents  
            Hash--\>\>Indexer: Discard Block (Duplicate)  
        end  
    end  
      
    Indexer-\>\>Indexer: Sort chronologically by timestamp  
    Indexer-\>\>MD: generate\_markdown()  
    MD--\>\>Indexer: Return Cleaned Transcript

## **5\. Component & Module Dependency Diagram**

This structural diagram maps out how your Python files depend on one another, highlighting the clean separation of concerns in your src/ directory.

graph TD  
    App\[\<code\>app.py\</code\>\<br/\>Streamlit Frontend\] \--\> Engine\[\<code\>agent\_engine.py\</code\>\<br/\>API Proxy\]  
    App \--\> Logger\[\<code\>logger.py\</code\>\<br/\>Telemetry\]  
      
    Engine \--\> Graph\[\<code\>src/agents/graph.py\</code\>\<br/\>State Machine\]  
      
    Graph \--\> State\[\<code\>src/agents/state.py\</code\>\<br/\>TypedDicts\]  
    Graph \--\> Prompts\[\<code\>src/prompts/system\_prompts.py\</code\>\<br/\>Static Strings\]  
    Graph \--\> Retriever\[\<code\>src/tools/retriever.py\</code\>\<br/\>Advanced RAG\]  
    Graph \--\> Search\[\<code\>src/tools/search.py\</code\>\<br/\>Tavily Fallback\]  
    Graph \--\> Crusher\[\<code\>src/utils/text\_crusher.py\</code\>\<br/\>Regex Pruning\]  
      
    Evaluator\[\<code\>src/evaluator.py\</code\>\<br/\>EDD Benchmarking\] \--\> Graph  
      
    Parser\[\<code\>src/parser.py\</code\>\<br/\>Async PDF ETL\] \--\> Ingest\[\<code\>src/ingest.py\</code\>\<br/\>Vector DB Builder\]  
    MailIndex\[\<code\>src/mail\_indexer.py\</code\>\<br/\>Email ETL\] \--\> Ingest

    classDef python fill:\#2b313e,stroke:\#ffb300,stroke-width:1px,color:\#fff;  
    class App,Engine,Logger,Graph,State,Prompts,Retriever,Search,Crusher,Evaluator,Parser,Ingest,MailIndex python;

## **6\. Evaluation-Driven Development (EDD) Flow**

This sequence diagram outlines how the benchmark suite tests the agent against a verified Golden Dataset while navigating API rate limits.

sequenceDiagram  
    autonumber  
    participant Dataset as Golden Dataset (JSON)  
    participant Eval as evaluator.py (Runner)  
    participant Graph as LangGraph System  
    participant Judge as Evaluator LLM (8B)  
    participant DB as track.json (Results)

    Eval-\>\>Dataset: Read target queries & Ground Truth  
    Eval-\>\>DB: Check for existing checkpoint (Resume)  
      
    loop Over Each Benchmark Query  
        Eval-\>\>Graph: Invoke State Machine {query}  
          
        alt API Rate Limit Hit (429/TPD)  
            Graph--xEval: Throw Exception  
            Note over Eval: Catch 429\<br/\>Swap to Fallback Key\<br/\>Swap to OpenRouter if needed  
            Eval-\>\>Graph: Retry Invocation  
        end  
          
        Graph--\>\>Eval: Return Generated Audit  
          
        Eval-\>\>Judge: Send Audit \+ Ground Truth  
        Note over Judge: Enforce Strict JSON Mode:\<br/\>{accuracy\_score, statute\_match}  
        Judge--\>\>Eval: Return Scoring Metrics  
          
        Eval-\>\>DB: Append Result & Flush to Disk  
    end  
