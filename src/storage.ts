import type { Event } from './types';

const STORAGE_KEY = 'adhd-event-tracker-events';

export const storage = {
  getEvents(): Event[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (error) {
      console.error('Error reading from storage:', error);
      return [];
    }
  },

  saveEvents(events: Event[]): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
    } catch (error) {
      console.error('Error saving to storage:', error);
    }
  },

  addEvent(event: Event): void {
    const events = this.getEvents();
    events.unshift(event);
    this.saveEvents(events);
  },

  updateEvent(id: string, updatedEvent: Partial<Event>): void {
    const events = this.getEvents();
    const index = events.findIndex(e => e.id === id);
    if (index !== -1) {
      events[index] = {
        ...events[index],
        ...updatedEvent,
        updatedAt: new Date().toISOString()
      };
      this.saveEvents(events);
    }
  },

  deleteEvent(id: string): void {
    const events = this.getEvents();
    const filtered = events.filter(e => e.id !== id);
    this.saveEvents(filtered);
  },

  clearAll(): void {
    localStorage.removeItem(STORAGE_KEY);
  }
};
