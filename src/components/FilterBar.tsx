import type { FilterOptions, EventCategory } from '../types';
import { CATEGORY_LABELS } from '../types';

interface FilterBarProps {
  filters: FilterOptions;
  onFiltersChange: (filters: FilterOptions) => void;
  totalEvents: number;
  filteredCount: number;
}

export default function FilterBar({ filters, onFiltersChange, totalEvents, filteredCount }: FilterBarProps) {
  const handleCategoryChange = (category: EventCategory | '') => {
    onFiltersChange({
      ...filters,
      category: category || undefined,
    });
  };

  const handleSearchChange = (searchQuery: string) => {
    onFiltersChange({
      ...filters,
      searchQuery: searchQuery || undefined,
    });
  };

  const handleImportantToggle = () => {
    onFiltersChange({
      ...filters,
      important: filters.important === true ? undefined : true,
    });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  const hasActiveFilters = filters.category || filters.searchQuery || filters.important !== undefined;

  return (
    <div className="focus-card mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800">Filters</h2>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Search */}
        <div>
          <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">
            Search
          </label>
          <input
            type="text"
            id="search"
            value={filters.searchQuery || ''}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Search events, tags..."
          />
        </div>

        {/* Category Filter */}
        <div>
          <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            id="category-filter"
            value={filters.category || ''}
            onChange={(e) => handleCategoryChange(e.target.value as EventCategory | '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">All Categories</option>
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Important Toggle */}
        <div className="flex items-end">
          <button
            onClick={handleImportantToggle}
            className={`w-full px-4 py-2 rounded-lg font-medium transition-colors ${
              filters.important
                ? 'bg-yellow-400 text-yellow-900 hover:bg-yellow-500'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {filters.important ? '⭐ Important Only' : '☆ Show All'}
          </button>
        </div>
      </div>

      {/* Results count */}
      {totalEvents > 0 && (
        <div className="mt-4 text-sm text-gray-600">
          Showing {filteredCount} of {totalEvents} events
        </div>
      )}
    </div>
  );
}
