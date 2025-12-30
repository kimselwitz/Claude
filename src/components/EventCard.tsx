import type { Event } from '../types';
import { CATEGORY_LABELS, CATEGORY_COLORS } from '../types';

interface EventCardProps {
  event: Event;
  onEdit: (event: Event) => void;
  onDelete: (id: string) => void;
  onToggleImportant: (id: string) => void;
}

export default function EventCard({ event, onEdit, onDelete, onToggleImportant }: EventCardProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const diffTime = today.getTime() - date.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={`focus-card border-l-4 ${event.important ? 'border-yellow-400 bg-yellow-50' : 'border-transparent'}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header Row */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${CATEGORY_COLORS[event.category]}`}>
              {CATEGORY_LABELS[event.category]}
            </span>
            <span className="text-sm text-gray-500">
              {formatDate(event.date)}
            </span>
            {event.important && (
              <span className="text-yellow-500 text-lg" title="Important">⭐</span>
            )}
          </div>

          {/* Title */}
          <h3 className="text-xl font-bold text-gray-800 mb-2">
            {event.title}
          </h3>

          {/* Description */}
          {event.description && (
            <p className="text-gray-600 mb-3 whitespace-pre-wrap">
              {event.description}
            </p>
          )}

          {/* Tags */}
          {event.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {event.tags.map((tag, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-gray-200 text-gray-700 text-xs rounded"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}

          {/* Metadata */}
          <div className="text-xs text-gray-400">
            Created {new Date(event.createdAt).toLocaleString()}
            {event.updatedAt !== event.createdAt && (
              <> • Updated {new Date(event.updatedAt).toLocaleString()}</>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          <button
            onClick={() => onToggleImportant(event.id)}
            className="p-2 hover:bg-yellow-100 rounded transition-colors"
            title={event.important ? 'Unmark as important' : 'Mark as important'}
          >
            {event.important ? '⭐' : '☆'}
          </button>
          <button
            onClick={() => onEdit(event)}
            className="p-2 hover:bg-blue-100 rounded transition-colors"
            title="Edit"
          >
            ✏️
          </button>
          <button
            onClick={() => onDelete(event.id)}
            className="p-2 hover:bg-red-100 rounded transition-colors"
            title="Delete"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>
  );
}
