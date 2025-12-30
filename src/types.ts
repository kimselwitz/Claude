export type EventCategory =
  | 'life-event'
  | 'message'
  | 'social-post'
  | 'reminder'
  | 'achievement'
  | 'other';

export interface Event {
  id: string;
  title: string;
  description: string;
  category: EventCategory;
  date: string;
  tags: string[];
  important: boolean;
  createdAt: string;
  updatedAt: string;
}

export type FilterOptions = {
  category?: EventCategory;
  searchQuery?: string;
  tags?: string[];
  important?: boolean;
};

export const CATEGORY_LABELS: Record<EventCategory, string> = {
  'life-event': '🎉 Life Event',
  'message': '💬 Message',
  'social-post': '📱 Social Post',
  'reminder': '⏰ Reminder',
  'achievement': '🏆 Achievement',
  'other': '📝 Other',
};

export const CATEGORY_COLORS: Record<EventCategory, string> = {
  'life-event': 'bg-purple-100 border-purple-300 text-purple-800',
  'message': 'bg-blue-100 border-blue-300 text-blue-800',
  'social-post': 'bg-pink-100 border-pink-300 text-pink-800',
  'reminder': 'bg-yellow-100 border-yellow-300 text-yellow-800',
  'achievement': 'bg-green-100 border-green-300 text-green-800',
  'other': 'bg-gray-100 border-gray-300 text-gray-800',
};
