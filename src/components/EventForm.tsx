import { useState } from 'react';
import type { Event, EventCategory } from '../types';
import { CATEGORY_LABELS } from '../types';

interface EventFormProps {
  onSubmit: (event: Omit<Event, 'id' | 'createdAt' | 'updatedAt'>) => void;
  onCancel: () => void;
  initialData?: Event;
  isEditing?: boolean;
}

export default function EventForm({ onSubmit, onCancel, initialData, isEditing }: EventFormProps) {
  const [title, setTitle] = useState(initialData?.title || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [category, setCategory] = useState<EventCategory>(initialData?.category || 'other');
  const [date, setDate] = useState(initialData?.date || new Date().toISOString().split('T')[0]);
  const [tags, setTags] = useState(initialData?.tags.join(', ') || '');
  const [important, setImportant] = useState(initialData?.important || false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      alert('Please enter a title');
      return;
    }

    onSubmit({
      title: title.trim(),
      description: description.trim(),
      category,
      date,
      tags: tags.split(',').map(t => t.trim()).filter(Boolean),
      important,
    });

    if (!isEditing) {
      setTitle('');
      setDescription('');
      setCategory('other');
      setDate(new Date().toISOString().split('T')[0]);
      setTags('');
      setImportant(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="focus-card">
      <h2 className="text-2xl font-bold mb-4 text-gray-800">
        {isEditing ? 'Edit Event' : 'Add New Event'}
      </h2>

      <div className="space-y-4">
        {/* Title */}
        <div>
          <label htmlFor="title" className="block text-sm font-semibold text-gray-700 mb-1">
            Title *
          </label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Quick title for your event"
            autoFocus
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-semibold text-gray-700 mb-1">
            Description
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="More details about this event..."
            rows={3}
          />
        </div>

        {/* Category and Date Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Category */}
          <div>
            <label htmlFor="category" className="block text-sm font-semibold text-gray-700 mb-1">
              Category
            </label>
            <select
              id="category"
              value={category}
              onChange={(e) => setCategory(e.target.value as EventCategory)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Date */}
          <div>
            <label htmlFor="date" className="block text-sm font-semibold text-gray-700 mb-1">
              Date
            </label>
            <input
              type="date"
              id="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Tags */}
        <div>
          <label htmlFor="tags" className="block text-sm font-semibold text-gray-700 mb-1">
            Tags
          </label>
          <input
            type="text"
            id="tags"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="work, family, friends (comma separated)"
          />
        </div>

        {/* Important Checkbox */}
        <div className="flex items-center">
          <input
            type="checkbox"
            id="important"
            checked={important}
            onChange={(e) => setImportant(e.target.checked)}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <label htmlFor="important" className="ml-2 text-sm font-semibold text-gray-700">
            ⭐ Mark as important
          </label>
        </div>

        {/* Buttons */}
        <div className="flex gap-3 pt-2">
          <button type="submit" className="btn-primary flex-1">
            {isEditing ? 'Update Event' : 'Save Event'}
          </button>
          <button type="button" onClick={onCancel} className="btn-secondary">
            Cancel
          </button>
        </div>
      </div>
    </form>
  );
}
