# 🧠 Productivity Tracker

A simple, distraction-free web application designedto keep track of important life events, messages, social media posts, achievements, and more.

## Features

- **Quick Capture**: Easily add events with minimal clicks
- **Visual Categories**: Color-coded categories for different event types
  - 🎉 Life Events
  - 💬 Messages
  - 📱 Social Posts
  - ⏰ Reminders
  - 🏆 Achievements
  - 📝 Other
- **Search & Filter**: Find events quickly with search and category filters
- **Important Marking**: Star events to mark them as important
- **Tags**: Organize events with custom tags
- **Timeline View**: See all your events in chronological order
- **Local Storage**: All data is saved locally in your browser
- **Stats Dashboard**: Track your events with visual statistics

## Tech Stack

- React 18 with TypeScript
- Vite for fast development
- Tailwind CSS for styling
- Local Storage for data persistence

## Getting Started

### Prerequisites

- Node.js (version 16 or higher)
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd adhd-event-tracker
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser and navigate to `http://localhost:5173`

### Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Usage

### Adding an Event

1. Click the "Quick Add Event" button
2. Fill in the title (required)
3. Optionally add a description, select a category, set a date, and add tags
4. Check "Mark as important" for important events
5. Click "Save Event"

### Filtering Events

- Use the search bar to find events by title, description, or tags
- Select a category from the dropdown to filter by event type
- Click "Important Only" to see only starred events
- Click "Clear all" to reset filters

### Editing Events

- Click the edit (✏️) button on any event card
- Make your changes in the form
- Click "Update Event" to save

### Deleting Events

- Click the delete (🗑️) button on any event card
- Confirm the deletion

## Project Structure

```
src/
├── components/
│   ├── EventCard.tsx      # Individual event display
│   ├── EventForm.tsx      # Form for adding/editing events
│   └── FilterBar.tsx      # Search and filter controls
├── types.ts               # TypeScript type definitions
├── storage.ts             # Local storage utilities
├── App.tsx                # Main application component
├── App.css                # Application styles
├── index.css              # Global styles with Tailwind
└── main.tsx               # Application entry point
```

## ADHD-Friendly Design Principles

This app is designed with ADHD users in mind:

- **Minimal Distractions**: Clean, simple interface with no unnecessary elements
- **Quick Capture**: Fast event creation with minimal required fields
- **Visual Organization**: Color-coded categories and clear visual hierarchy
- **Easy Filtering**: Quick access to specific events without overwhelming choices
- **Forgiving UX**: Confirmation dialogs for destructive actions
- **No Account Required**: Works offline, no sign-up needed

## Data Privacy

All your data is stored locally in your browser using LocalStorage. Nothing is sent to any server. Your events are private and remain on your device.

## Browser Support

Works on all modern browsers that support:
- LocalStorage
- ES6+
- CSS Grid and Flexbox

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## License

MIT License - feel free to use this project for personal or commercial purposes.

## Acknowledgments

Built with care for the ADHD community. If you find this helpful, please share it with others who might benefit!
