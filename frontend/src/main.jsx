import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: String(error?.message || error) };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 16, fontFamily: "Segoe UI, Arial, sans-serif" }}>
          <h2>Frontend Runtime Error</h2>
          <p>UI fallback is active so the screen is never blank.</p>
          <pre style={{ whiteSpace: "pre-wrap" }}>{this.state.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootElement = document.getElementById("root");

if (!rootElement) {
  document.body.innerHTML =
    "<div style='padding:16px;font-family:Segoe UI,Arial,sans-serif'>Root mount failed: missing #root element.</div>";
} else {
  createRoot(rootElement).render(
    <React.StrictMode>
      <RootErrorBoundary>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </RootErrorBoundary>
    </React.StrictMode>
  );
}
