# MCPHawk Frontend

Modern Vue 3 frontend for MCPHawk - a passive network sniffer for Model Context Protocol traffic.

## Tech Stack

- **Vue 3** - Progressive JavaScript framework
- **Vite** - Lightning fast build tool
- **Pinia** - State management
- **Tailwind CSS** - Utility-first CSS framework
- **Headless UI** - Unstyled accessible components

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development server (runs on http://localhost:5173)
npm run dev

# Build for production (outputs to ../mcphawk/web/static)
npm run build
```

### Development Workflow

1. **Frontend only development:**
   ```bash
   npm run dev
   ```
   The Vite dev server proxies API calls to `http://localhost:8000`

2. **Full stack development:**
   ```bash
   # From project root
   make dev
   ```
   This runs both frontend and backend concurrently

## Architecture

### Components

- **LogTable/** - Main log display with virtual scrolling
  - `LogTable.vue` - Table container
  - `LogRow.vue` - Individual log row
  - `LogFilters.vue` - Filter controls
  - `MessageTypeBadge.vue` - Type indicators

- **MessageDetail/** - Detailed message view
  - `MessageDetailModal.vue` - Modal for viewing full messages

- **Stats/** - Statistics display
  - `StatsPanel.vue` - Real-time stats

- **common/** - Shared components
  - `ConnectionStatus.vue` - WebSocket connection indicator
  - `ThemeToggle.vue` - Dark/light mode switch

### State Management (Pinia)

- **logs.js** - Log data and filtering
- **websocket.js** - WebSocket connection management

### Utilities

- **messageParser.js** - JSON-RPC message parsing and formatting

## Contributing

1. Follow Vue 3 Composition API patterns
2. Use Tailwind utilities over custom CSS
3. Ensure components are accessible
4. Add appropriate TypeScript types (when we migrate)
5. Test on both light and dark themes