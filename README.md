<div align="center">

# 🚀 Ission Agent

### Turn GitHub Issues into Architecture-Aware Development Plans

Powered by Azure AI Foundry, Google Gemini and Multi-Stage AI Reasoning.

![Demo](assets/demo.gif)

![Angular](https://img.shields.io/badge/Angular-19-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Azure AI Foundry](https://img.shields.io/badge/Azure_AI_Foundry-RAG_Enabled-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-AI_Core-4285F4?style=for-the-badge&logo=google&logoColor=white)
</div>



# 🚨 The Problem

Before a developer can fix an issue, someone must:

- Understand the problem
- Identify missing information
- Check architectural constraints
- Define an implementation strategy

This process is often manual, repetitive, and dependent on senior engineers.



# 💡 The Solution

Ission Agent automates issue triage through a multi-stage reasoning workflow.

Given a GitHub issue, the agent:

✅ Evaluates issue quality

✅ Classifies the issue using Azure AI Foundry

✅ Retrieves project-specific architecture guidelines

✅ Generates an implementation plan

✅ Reviews its own output through a Critic Agent

✅ Publishes the final plan back to GitHub



# 🧠 Reasoning Pipeline

```text
GitHub Issue
      │
      ▼
Issue Quality Score
      │
      ▼
Foundry IQ Classification
      │
      ▼
Architecture Context (RAG)
      │
      ▼
Planner Agent (Gemini)
      │
      ▼
Critic Agent (Gemini)
      │
      ▼
GitHub Comment
```



# 🏗️ System Architecture

```text
┌────────────────────┐
│ Angular Frontend   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ FastAPI Backend    │
│ Orchestrator       │
└──────┬─────┬───────┘
       │     │
       │     └────► Azure AI Foundry
       │           (Classification + RAG)
       │
       ├──────────► GitHub API
       │
       └──────────► Google Gemini
                   (Planning + Critic)
```



# ✨ Key Features

- Issue Quality Scoring
- Azure AI Foundry Classification
- Architecture-Aware Planning
- Retrieval-Augmented Generation (RAG)
- Critic Agent Validation
- GitHub Comment Publishing
- OAuth Authentication
- Transparent Thought Stream Visualization


# 🛠️ Tech Stack

### Frontend

- Angular
- TypeScript
- SCSS

### Backend

- FastAPI
- Python
- AsyncIO

### AI Layer

- Azure AI Foundry
- Azure AI Search
- Google Gemini

### Integrations

- GitHub API
- GitHub OAuth



# 🚀 Quick Start

### Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload
```

### Frontend

```bash
cd frontend

npm install

ng serve
```



# 📂 Project Structure

```text
ission-agent/
│
├── frontend/
│
├── backend/
│   ├── main.py
│   ├── orchestrator.py
│
└── README.md
```



# 🔮 Future Work

- Pull Request Generation
- Repository-Wide Code Understanding
- Multi-Agent Collaboration
- Microsoft Agent Framework Integration



## Built for the Microsoft Agents League Hackathon

Ission Agent demonstrates how Azure AI Foundry and LLM reasoning can reduce the time spent understanding and planning software work before implementation begins.
