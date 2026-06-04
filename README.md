<div align='center'> <h1>Ission Agent</h1> </div>

An autonomous AI-powered developer assistant designed to analyze GitHub issues, generate structured implementation plans, and streamline technical triage workflows.

## Overview

Ission Agent was created to automate one of the most repetitive tasks in software development teams: understanding, analyzing, and planning the resolution of GitHub issues.

In many organizations, senior developers and tech leads spend valuable time reviewing reported issues, identifying requirements, outlining technical approaches, and documenting next steps before assigning work to the engineering team.

Ission Agent reduces this overhead by acting as an intelligent orchestration layer between GitHub and Large Language Models (LLMs), transforming raw issue reports into actionable development plans.

The system retrieves issue data directly from GitHub, processes the content through an AI-driven workflow, and generates structured technical recommendations that can be reviewed and published back to the repository.


## Key Features

* GitHub Issue Analysis
* Automated Technical Planning
* AI-Powered Issue Understanding
* Structured Markdown Output
* GitHub Comment Publishing
* Secure Credential Management
* Decoupled Frontend and Backend Architecture
* Asynchronous Processing
* Developer-Friendly User Interface



## Architecture

The project follows a client-server architecture with clear separation of responsibilities.

```text
┌─────────────────┐
│     Angular     │
│    Frontend     │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│     FastAPI     │
│   Orchestrator  │
└────────┬────────┘
         │
         ├────────► GitHub API
         │
         └────────► Google Gemini API
```

### Frontend

The Angular application is responsible for:

* Collecting GitHub issue URLs
* Displaying agent reasoning steps
* Rendering AI-generated markdown responses
* Managing loading and error states
* Publishing generated plans

### Backend

The FastAPI backend acts as the orchestration layer responsible for:

* Receiving frontend requests
* Parsing GitHub issue URLs
* Fetching issue data from GitHub
* Communicating with AI models
* Generating implementation plans
* Publishing comments to GitHub
* Protecting API keys and access tokens

The frontend never communicates directly with external services, ensuring security and maintainability.

---

## Project Structure

```text
ission-agent/
│
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── app.component.ts
│   │       ├── app.component.html
│   │       └── app.component.scss
│   │
│   └── angular.json
│
├── backend/
│   ├── main.py
│   ├── orchestrator.py
│   ├── requirements.txt
│   └── .env
│
└── README.md
```

### Backend Components

#### `main.py`

Application entry point.

Responsibilities:

* FastAPI initialization
* Route definitions
* CORS configuration
* Request validation
* API exposure

#### `orchestrator.py`

Core business logic layer.

Responsibilities:

* GitHub integration
* AI orchestration
* Issue processing
* Response generation
* Comment publishing

This separation follows the **Separation of Concerns** design principle, keeping routing logic independent from business logic.


## Technology Stack

### Frontend

| Technology   | Purpose               |
| ------------ | --------------------- |
| Angular      | User interface        |
| TypeScript   | Type-safe development |
| RxJS         | Reactive programming  |
| ngx-markdown | Markdown rendering    |

### Backend

| Technology | Purpose                 |
| ---------- | ----------------------- |
| FastAPI    | REST API framework      |
| Python     | Business logic          |
| Uvicorn    | ASGI server             |
| AsyncIO    | Asynchronous processing |

### External Services

| Service       | Purpose                                |
| ------------- | -------------------------------------- |
| GitHub API    | Issue retrieval and comment publishing |
| Google Gemini | AI-powered analysis and planning       |



## Application Flow

### 1. User Input

The user submits a GitHub issue URL.

Example:

```text
https://github.com/facebook/react/issues/1
```

### 2. Frontend Request

The Angular application sends a POST request to the FastAPI backend.

### 3. URL Processing

The orchestrator extracts:

* Repository owner
* Repository name
* Issue number

### 4. GitHub Retrieval

The backend requests issue information from GitHub and retrieves:

* Title
* Description
* Metadata

### 5. AI Analysis

The issue content is processed by the AI workflow, generating:

* Issue understanding
* Technical assessment
* Recommended implementation strategy
* Actionable development plan

### 6. Response Delivery

The backend returns:

```json
{
  "status": "success",
  "thoughts": [],
  "finalComment": ""
}
```

### 7. Frontend Rendering

The generated markdown is rendered dynamically in the user interface.

### 8. Publishing

The user may publish the generated plan directly as a GitHub issue comment.

---

## Security

Sensitive information is stored using environment variables.

Example:

```env
GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_api_key
```

The `.env` file should never be committed to source control.

Recommended `.gitignore` entry:

```gitignore
.env
```

---

## Local Development

### Prerequisites

* Node.js 20+
* Angular CLI
* Python 3.11+
* GitHub Personal Access Token
* Google Gemini API Key

---

### Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GITHUB_TOKEN=your_token
GEMINI_API_KEY=your_api_key
```

Run the API:

```bash
uvicorn main:app --reload
```

Backend available at:

```text
http://localhost:8000
```



### Frontend Setup

Navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the Angular application:

```bash
ng serve
```

Frontend available at:

```text
http://localhost:4200
```

---

## Design Principles

The project was built around the following engineering principles:

* Separation of Concerns
* Client-Server Architecture
* Secure Credential Management
* Asynchronous Processing
* Scalability
* Maintainability
* Modular Design



## Future Improvements

Potential future enhancements include:

* Multi-agent workflows
* Repository-wide context analysis
* Pull Request generation
* Semantic codebase search
* Issue prioritization
* Team assignment suggestions
* RAG-based repository understanding
* Azure AI Foundry integration
* Microsoft Agent Framework integration



## License

This project was developed as part of a hackathon initiative and is intended for educational, experimental, and portfolio purposes.
