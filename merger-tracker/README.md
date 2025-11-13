# ACCC Merger Tracker

A modern web application for tracking and analyzing ACCC merger reviews. This application provides an intuitive interface for legal advisors and the public to monitor merger progress, view statistics, and analyze trends over time.

## Features

- **dashboard**: Overview with key statistics and visualizations
- **merger list**: Searchable and filterable list of all mergers
- **detailed views**: Comprehensive information for each merger including timeline and events
- **timeline view**: Chronological display of all mergers
- **industry analysis**: ANZSIC industry classifications and merger counts
- **charts & analytics**: Phase duration analysis, approval rates, and more

## Architecture

### Backend
- **FastAPI**: Modern Python web framework
- **SQLite**: Lightweight database for merger data
- **RESTful API**: Clean API endpoints for data access

### Frontend
- **React**: Modern component-based UI
- **Tailwind CSS**: Utility-first CSS framework
- **Chart.js**: Beautiful data visualizations
- **React Router**: Client-side routing

## Quick start

### Prerequisites
- Python 3.8+
- Node.js 20+
- npm or yarn

### Backend setup

1. Navigate to the backend directory:
```bash
cd merger-tracker/backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Sync data from the parent repository:
```bash
python sync_data.py
```

5. Start the API server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### Frontend setup

1. Navigate to the frontend directory:
```bash
cd merger-tracker/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## API endpoints

- `GET /api/mergers` - List all mergers with optional filters
- `GET /api/mergers/{id}` - Get detailed information about a merger
- `GET /api/stats` - Get aggregated statistics
- `GET /api/timeline` - Get timeline data for all mergers
- `GET /api/industries` - Get industry classifications with merger counts

## Data sync

To keep the database updated with the latest merger data:

```bash
cd backend
python sync_data.py
```

This script reads the `mergers.json` file from the parent repository and updates the SQLite database.

## Production deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions on deploying to:
- DigitalOcean
- AWS (EC2, ECS, or Elastic Beanstalk)
- Docker-based deployments

## Configuration

### Backend configuration
Copy `.env.example` to `.env` and adjust settings:
```bash
PORT=8000
HOST=0.0.0.0
ALLOWED_ORIGINS=https://your-domain.com
DATABASE_PATH=mergers.db
```

### Frontend configuration
Copy `.env.example` to `.env` and set the API URL:
```bash
VITE_API_URL=https://api.your-domain.com
```

## Development

### Backend development
```bash
cd backend
uvicorn main:app --reload
```

### Frontend development
```bash
cd frontend
npm run dev
```

### Building for production

Frontend:
```bash
cd frontend
npm run build
```

The built files will be in the `dist` directory.

## License

[Add your license here]
