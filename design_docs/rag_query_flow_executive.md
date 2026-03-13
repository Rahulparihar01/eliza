# RAG Query Flow - Executive Overview

How the system answers questions while protecting client data.

---

```mermaid
flowchart TB
    subgraph Input["👤 USER"]
        User["Asks a question in plain English"]
    end

    subgraph Auth["🔐 ACCESS CONTROL"]
        Okta["Okta verifies identity"]
        Permissions["System checks permissions"]
        
        subgraph Access["User's Data Access"]
            direction LR
            Firm["✅ Firm-Wide"]
            ClientA["✅ Client A"]
            ClientB["❌ Client B"]
        end
    end

    subgraph Search["🔍 SECURE SEARCH"]
        Filter["Search ONLY<br/>authorized documents"]
        
        subgraph Sources["Document Sources"]
            direction LR
            FirmDocs["Firm Policies"]
            ClientADocs["Client A Memos"]
        end
        
        Blocked["🚫 Client B data<br/>automatically excluded"]
    end

    subgraph AI["🤖 AI PROCESSING"]
        Context["Relevant content<br/>assembled"]
        LLM["AI generates<br/>response"]
        Citations["Sources cited"]
    end

    subgraph Output["📊 RESPONSE"]
        Answer["Clear answer with<br/>document citations"]
    end

    subgraph Compliance["📋 AUDIT"]
        Log["Query, user, documents<br/>logged for 7 years"]
    end

    User --> Okta
    Okta --> Permissions
    Permissions --> Access
    Access --> Filter
    Filter --> Sources
    Filter -.-> Blocked
    Sources --> Context
    Context --> LLM
    LLM --> Citations
    Citations --> Answer
    Answer --> Log

    style User fill:#FFF2ED,stroke:#FF9580,stroke-width:2px
    style Okta fill:#FFE4DC,stroke:#FF7B6B,stroke-width:2px
    style Permissions fill:#FFE4DC,stroke:#FF7B6B,stroke-width:1px
    style Firm fill:#D1FAE5,stroke:#19C37D,stroke-width:1px
    style ClientA fill:#D1FAE5,stroke:#19C37D,stroke-width:1px
    style ClientB fill:#FEE2E2,stroke:#EF4444,stroke-width:1px
    style Filter fill:#F8F5F0,stroke:#8B3A52,stroke-width:2px
    style FirmDocs fill:#FFF2ED,stroke:#FF9580,stroke-width:1px
    style ClientADocs fill:#FFF2ED,stroke:#FF9580,stroke-width:1px
    style Blocked fill:#FEE2E2,stroke:#EF4444,stroke-width:1px,stroke-dasharray: 5 5
    style Context fill:#EDE9FE,stroke:#8B5CF6,stroke-width:1px
    style LLM fill:#EDE9FE,stroke:#8B5CF6,stroke-width:2px
    style Citations fill:#EDE9FE,stroke:#8B5CF6,stroke-width:1px
    style Answer fill:#D1FAE5,stroke:#19C37D,stroke-width:2px
    style Log fill:#F8F5F0,stroke:#C96B75,stroke-width:2px
```

---

## Key Safeguards

| Protection | How It Works |
|------------|--------------|
| 🔐 **Identity Verification** | User identity confirmed via Okta before every query |
| 📁 **Data Isolation** | Each client's documents stored in separate collections |
| 🚫 **Access Enforcement** | System only searches documents user is authorized to see |
| 📋 **Full Audit Trail** | Every query logged with user, time, and documents accessed |
| ⚠️ **Clear Denials** | If user asks about restricted data, system explains why |

---

> **Bottom Line:** Users can only see data they're authorized to access. The system enforces this automatically, logs everything for compliance, and provides clear feedback when access is denied.

