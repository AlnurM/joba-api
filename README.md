# FastAPI MongoDB Project

A simple FastAPI project using MongoDB.

## Requirements

- Python 3.8+
- MongoDB
- pip (Python package manager)

## Installation

1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # for Linux/Mac
# or
.\venv\Scripts\activate  # for Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Make sure MongoDB is running on your machine

## Running the Application

1. Start the server:
```bash
uvicorn main:app --reload
```

2. Open your browser and navigate to: http://localhost:8000

3. API documentation is available at: http://localhost:8000/docs 