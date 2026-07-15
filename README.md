# AI-First CRM (HCP Interaction Module)

An AI-first Customer Relationship Management (CRM) system for Healthcare Professionals (HCPs). Instead of manually entering long form data, sales representatives describe meetings in natural language. The backend LangGraph agent extracts structured details, executes business tools, and automatically populates the CRM form on the frontend.

---

## 🚀 Key Features

* **Conversational Logging**: Enter interaction details via natural chat. The AI assistant extracts parameters and auto-fills the structured form.
* **Granular Edit Tool**: Update specific logs (e.g. *"Change sentiment to Neutral"*) without affecting other fields or losing the doctor's name.
* **HCP Search**: Look up medical professionals by name, specialty, or hospital directly from the chat interface.
* **Auto-generated Follow-up Emails**: Instantly draft formal business emails tailored to the outcomes of the interaction.
* **Next Best Action recommendation**: Provide clinical strategy recommendations based on discussion topics and physician sentiment.

---

## 🛠 Tech Stack

* **Frontend**: React, Redux (State Management), Vanilla CSS
* **Backend**: FastAPI (Python), Uvicorn
* **AI Orchestration**: LangGraph (React agent workflow), LangChain
* **LLM**: Groq (`llama-3.3-70b-versatile` / `gemma2-9b-it`) or Google Gemini (`gemini-1.5-flash`)
* **Database**: MySQL (Relational storage)

---

## 📂 Project Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints & routing (FastAPI)
│   │   ├── core/           # Configuration settings (.env loading)
│   │   ├── database/       # MySQL session management & schema setup
│   │   ├── langgraph/      # Conversational Agent workflow
│   │   └── tools/          # LangChain custom tools (Log, Edit, Search, Email, Next Action)
│   ├── .env.example        # Environment template file
│   └── requirements.txt    # Backend dependencies
├── frontend/
│   ├── src/
│   │   ├── api/            # API communication clients
│   │   ├── components/     # UI Shell Layout
│   │   └── pages/          # Main CRM page (structured form & assistant chat)
│   └── package.json        # Frontend configuration
├── docker-compose.yml      # Service orchestration
└── README.md               # Documentation
```

---

## ⚙️ Local Setup Instructions

### 1. Database Setup
Ensure you have a running MySQL server. 
1. Create a MySQL database (e.g. named `crm`).
2. The backend will automatically create tables (`interactions`, `hcps`, `materials`, `samples`, `follow_ups`) and seed mock Healthcare Professional data upon startup.

### 2. Backend Setup
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables. Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   Configure the following in your `.env`:
   ```env
   GROQ_API_KEY=your_groq_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DATABASE=crm
   ```
5. Run the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The backend will be live on: `http://localhost:8000`

### 3. Frontend Setup
1. Navigate to the frontend folder:
   ```bash
   cd ../frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Launch the development server:
   ```bash
   npm run dev
   ```
   The frontend will be live on: `http://localhost:3000`

---

## 🤖 AI Assistant Prompts for Testing

Here are sample prompts you can enter in the **AI Assistant** chat panel to test the custom tools:

* **Search HCP**: `Search HCPs named Sarah`
* **Log Interaction**: `Met Dr. Sarah Jenkins today, we had an In-person meeting. John and Clara also attended. We discussed CardioBest efficacy. Her sentiment was positive, and she agreed to evaluate the product. She requested 10 samples and the Phase III clinical brochure. Follow up in 2 weeks.`
* **Next Best Action**: `What is the next best action for Dr. Sarah Jenkins?`
* **Generate Email**: `Generate a follow-up email draft for Dr. Sarah Jenkins.`
* **Edit Interaction**: `Change the sentiment to Neutral and change follow-up to next Friday.` *(Note: edits the active interaction loaded in the form).*

  **Thank you**
