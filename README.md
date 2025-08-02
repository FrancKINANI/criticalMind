# CriticalMind SaaS Project

This repository contains the complete codebase for the CriticalMind SaaS application, which is designed to help users develop critical thinking and problem-solving skills.

## Project Structure

The project is organized into the following directories:

### `backend/`
Contains the backend application for the CriticalMind SaaS platform:
- Backend API built with Flask
- Database models and migrations
- Authentication and user management
- Payment processing integration (Stripe)
- Learning and gamification features

### `frontend/`
Contains the frontend application built with React and Vite:
- User interface for the CriticalMind platform
- Interactive components for learning and problem-solving
- Responsive design using Tailwind CSS

### `documentation/`
Contains project documentation and planning materials:
- `content.txt` - Project description and planning notes

## Getting Started

### Backend Setup
1. Navigate to the `backend/` directory
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run the application: `python src/main.py`

### Frontend Setup
1. Navigate to the `frontend/` directory
2. Install dependencies: `pnpm install`
3. Start the development server: `pnpm dev`

## Development

The backend runs on port 5000 by default, and the frontend runs on port 3000 by default.

For production deployment, the backend serves the frontend static files directly.
