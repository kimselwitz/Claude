import { useState, useEffect, useMemo } from 'react';
import type { Event, FilterOptions } from './types';
import { storage } from './storage';
import EventForm from './components/EventForm';
import EventCard from './components/EventCard';
import FilterBar from './components/FilterBar';
import './App.css';

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [filters, setFilters] = useState<FilterOptions>({});

  useEffect(() => {
    setEvents(storage.getEvents());
  }, []);

  const filteredEvents = useMemo(() => {
    return events.filter(event => {
      if (filters.category && event.category !== filters.category) {
        return false;
      }
      if (filters.important !== undefined && event.important !== filters.important) {
        return false;
      }
      if (filters.searchQuery) {
        const query = filters.searchQuery.toLowerCase();
        return (
          event.title.toLowerCase().includes(query) ||
          event.description.toLowerCase().includes(query) ||
          event.tags.some(tag => tag.toLowerCase().includes(query))
        );
      }
      return true;
    });
  }, [events, filters]);

  const handleAddEvent = (eventData: Omit<Event, 'id' | 'createdAt' | 'updatedAt'>) => {
    const newEvent: Event = {
      ...eventData,
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    storage.addEvent(newEvent);
    setEvents([newEvent, ...events]);
    setShowForm(false);
  };

  const handleUpdateEvent = (id: string, eventData: Partial<Event>) => {
    storage.updateEvent(id, eventData);
    setEvents(events.map(e => e.id === id ? { ...e, ...eventData, updatedAt: new Date().toISOString() } : e));
    setEditingEvent(null);
  };

  const handleDeleteEvent = (id: string) => {
    if (confirm('Are you sure you want to delete this event?')) {
      storage.deleteEvent(id);
      setEvents(events.filter(e => e.id !== id));
    }
  };

  const handleToggleImportant = (id: string) => {
    const event = events.find(e => e.id === id);
    if (event) {
      handleUpdateEvent(id, { important: !event.important });
    }
  };

  const handleEditEvent = (event: Event) => {
    setEditingEvent(event);
    setShowForm(true);
  };

  const handleCancelForm = () => {
    setShowForm(false);
    setEditingEvent(null);
  };

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">
            🧠 ADHD Event Tracker
          </h1>
          <p className="text-gray-600">
            Keep track of important life events, messages, and more
          </p>
        </header>

        {/* Quick Add Button */}
        <div className="mb-6">
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-primary text-lg"
          >
            {showForm ? '✕ Cancel' : '+ Quick Add Event'}
          </button>
        </div>

        {/* Event Form */}
        {showForm && (
          <div className="mb-8">
            <EventForm
              onSubmit={editingEvent ?
                (data) => handleUpdateEvent(editingEvent.id, data) :
                handleAddEvent
              }
              onCancel={handleCancelForm}
              initialData={editingEvent || undefined}
              isEditing={!!editingEvent}
            />
          </div>
        )}

        {/* Filter Bar */}
        <FilterBar
          filters={filters}
          onFiltersChange={setFilters}
          totalEvents={events.length}
          filteredCount={filteredEvents.length}
        />

        {/* Events List */}
        <div className="space-y-4">
          {filteredEvents.length === 0 ? (
            <div className="text-center py-12 focus-card">
              <p className="text-gray-500 text-lg">
                {events.length === 0
                  ? "No events yet. Click 'Quick Add Event' to get started!"
                  : "No events match your filters."
                }
              </p>
            </div>
          ) : (
            filteredEvents.map(event => (
              <EventCard
                key={event.id}
                event={event}
                onEdit={handleEditEvent}
                onDelete={handleDeleteEvent}
                onToggleImportant={handleToggleImportant}
              />
            ))
          )}
        </div>

        {/* Stats Footer */}
        {events.length > 0 && (
          <footer className="mt-8 pt-8 border-t border-gray-300">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div className="focus-card">
                <p className="text-2xl font-bold text-blue-600">{events.length}</p>
                <p className="text-sm text-gray-600">Total Events</p>
              </div>
              <div className="focus-card">
                <p className="text-2xl font-bold text-yellow-600">
                  {events.filter(e => e.important).length}
                </p>
                <p className="text-sm text-gray-600">Important</p>
              </div>
              <div className="focus-card">
                <p className="text-2xl font-bold text-green-600">
                  {events.filter(e => e.category === 'achievement').length}
                </p>
                <p className="text-sm text-gray-600">Achievements</p>
              </div>
              <div className="focus-card">
                <p className="text-2xl font-bold text-purple-600">
                  {events.filter(e => {
                    const daysSince = Math.floor(
                      (Date.now() - new Date(e.date).getTime()) / (1000 * 60 * 60 * 24)
                    );
                    return daysSince <= 7;
                  }).length}
                </p>
                <p className="text-sm text-gray-600">This Week</p>
              </div>
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}

export default App;
