# LoLLMs Chat - Vue Frontend

This directory contains the source code for the modern LoLLMs Chat frontend, built with Vue 3, Vite, and Pinia. This application provides a reactive, component-based, and maintainable user interface for interacting with the LoLLMs backend.

## ✨ Features

- **Modern Tech Stack:** Built with Vue 3 (`<script setup>`), Vite for fast development, and Pinia for robust state management.
- **Component-Based Architecture:** The UI is broken down into logical, reusable components for easier maintenance and development.
- **Centralized State Management:** Pinia stores manage application-wide state, such as authentication, discussions, and UI settings, ensuring data consistency.
- **Themable UI:** A CSS variable-driven design in `src/assets/css/main.css` allows for easy creation and switching of themes (e.g., light/dark).
- **Integrated Admin Panel:** User management is securely integrated into the main application and is only accessible to authenticated administrators.
- **Responsive Design:** The interface is designed to work smoothly on both desktop and mobile devices.

## 🛠️ Tech Stack

- **Framework:** [Vue.js 3](https://vuejs.org/)
- **Build Tool:** [Vite](https://vitejs.dev/)
- **State Management:** [Pinia](https://pinia.vuejs.org/)
- **Routing:** [Vue Router](https://router.vuejs.org/)
- **HTTP Client:** [Axios](https://axios-http.com/)
- **Styling:** [TailwindCSS](https://tailwindcss.com/)

## 🚀 Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) (version 18.x or higher recommended)
- The LoLLMs backend server running on its designated port (default is `9601`).

### Development

1.  **Navigate to the project directory:**
    ```bash
    cd frontend/webui
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Run the development server:**
    ```bash
    npm run dev
    ```
    The Vite development server will start, typically on `http://localhost:5173`. It features Hot Module Replacement (HMR) for a fast and efficient development experience.

    **Note:** The development server is pre-configured in `vite.config.js` to proxy all API requests (e.g., `/api/*`, `/admin/*`) to the backend server at `http://localhost:9601` to prevent CORS issues.

### Building for Production

To create a production-ready build of the application:

1.  **Run the build command:**
    ```bash
    npm run build
    ```
    This command will compile and minify the application assets into the `dist/` directory.

2.  **Serve the build:**
    The contents of the `dist/` directory can then be served by the main LoLLMs Python backend or any static file server.

## 📂 Project Structure

The source code is organized to promote modularity and separation of concerns.

-   `src/assets`: Global assets like CSS and images.
-   `src/components`: Reusable Vue components, categorized into `layout`, `chat`, `modals`, `admin`, and `ui`.
-   `src/router`: Vue Router configuration.
-   `src/services`: Centralized modules for external services (e.g., `api.js` for backend communication).
-   `src/stores`: Pinia state management modules.
-   `src/views`: Top-level components that represent application pages.
-   `src/App.vue`: The root Vue component.
-   `src/main.js`: The application's entry point.